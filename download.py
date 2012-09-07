#######################################################################
#AbsoluteURLGen copy pasted from http://www.python-forum.org/pythonforum/viewtopic.php?f=5&t=12515
#Have not *deeply* gone through the code or tested it much, other than the samples present in the above link, but it works for now.
#######################################################################
import re

class AbsoluteURLGen(object):
    def __init__(self, base='', replace_base=False):
        self.replace_base = replace_base
        self.base_regex = re.compile('^(https?://)(.*)$')
        self.base = self.normalize_base(base)
   
    def normalize_base(self, url):
        base = url
        if self.base_regex.search(base):
            # rid thyself of 'http(s)://'
            base = self.base_regex.search(url).group(2)
            if not base.rfind('/') == -1:
                # keep only the directory, not the filename
                base = base[:base.rfind('/')+1]
            base = self.base_regex.search(url).group(1) + base
        return base
       
    def get_absolute(self, url=''):
        if not self.base or (
                self.replace_base and self.base_regex.search(url)):
            self.base = self.normalize_base(url)
            return url
        elif self.base_regex.search(url):
            # it's an absolute url, but we don't want to keep it's base
            return url
        else:
            # now, it's time to do some converting.
            if url.startswith("../"):
                # they want the parent dir
                if not self.base[:-2].rfind("/") == -1:
                    base = self.base[:self.base[:-2].rfind("/")+1]
                    return base + url[3:]
                else:
                    # there are no subdirs... broken link?
                    return url
            elif url.startswith("/"):
                # file is in the root dir
                protocol, base = self.base_regex.search(self.base).groups()
                # remove subdirs until we're left with the root
                while not base[:-2].rfind("/") == -1:
                    base = base[:base[:-2].rfind('/')]
                return protocol + base + url
            else:
                if url.startswith("./"):
                    url = url[2:]
                return self.base + url

#######################################################################
import cookielib
import urllib2
import urllib
import argparse
import pprint
import os
import httplib
import sys
from bs4 import BeautifulSoup

class CourseraDownloader(object): 
    LOGIN_URL = 'https://www.coursera.org/maestro/api/user/login'
    REDIRECT_URL = 'https://class.coursera.org/{0}/auth/auth_redirector?type=login&subtype=normal&email=&visiting=%2F{0}%2Flecture%2Findex&minimal=true'

    def __init__(self,username,password):
        self.username = username
        self.password = password

        cj = cookielib.CookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

    def login(self):
        formParams = {
            'email_address': self.username,
            'password': self.password,
        }

        formParams = urllib.urlencode(formParams)
        self.opener.open(CourseraDownloader.LOGIN_URL, formParams)
        print "Successfully logged in as user " + self.username

    def course_name_from_url(self,course_url):
        return course_url.split('/')[3]

    def course_url_from_name(self,course_name):
        return "https://class.coursera.org/{0}/lecture/index".format(course_name)

    def get_downloadable_content(self,course_url):
        print "Collecting downloadable content from " + course_url
        course_name = self.course_name_from_url(course_url)
        u = CourseraDownloader.REDIRECT_URL.format(course_name)
        self.opener.open(u)
        r = self.opener.open(course_url)
        vidpage = r.read()
        soup = BeautifulSoup(vidpage)
        headers = soup.findAll("h3", { "class" : "list_header" })

        weeklyTopics = []
        allClasses = {}

        for header in headers:
            ul = header.findNext('ul')
            sanitisedHeaderName = sanitiseFileName(header.text)
            weeklyTopics.append(sanitisedHeaderName)
            lis = ul.findAll('li')
            weekClasses = {}

            classNames = []
            for li in lis:
                className = sanitiseFileName(li.a.text)
                classNames.append(className)
                classResources = li.find('div', {'class': 'item_resource'})

                hrefs = classResources.findAll('a')

                resourceLinks = []

                for href in hrefs:
                    resourceLinks.append(href['href'])

                weekClasses[className] = resourceLinks

            #This is needed to get the class names in the order they appear in the html
            weekClasses['classNames'] = classNames

            allClasses[sanitisedHeaderName] = weekClasses

        return (weeklyTopics, allClasses)

    def download(self, url, folder):
        #print url
        r = self.opener.open(url)

        if (CourseraDownloader.isHtml(r.headers)):
            print url, ' - is not downloadable'
            return

        #print r.headers.items()

        contentLength = CourseraDownloader.getContentLength(r.headers) 
        if not contentLength:
            contentLength = 16 * 1024
        fileName = sanitiseFileName(CourseraDownloader.getFileName(r.headers))
        if not fileName:
            fileName = CourseraDownloader.getFileNameFromURL(url)

        if os.path.exists(fileName):
            print fileName + " already exists, skipping"
        else:

            if (CourseraDownloader.isTextFile(fileName)):
                mode = 'w'
            else:
                mode = "wb"

            with open(fileName, mode) as fp:
              while True:
                chunk = r.read(contentLength)
                if not chunk: 
                    break
                fp.write(chunk)

    def download_course(self,course_url,dest_dir="."):

        cname = self.course_name_from_url(course_url)

        (weeklyTopics, allClasses) = self.get_downloadable_content(course_url)
        print 'Got all downloadable content for ' + cname

        target_dir = os.path.abspath(os.path.join(dest_dir,cname))
        print cname + " will be downloaded to " + target_dir

        for weeklyTopic in weeklyTopics:
            if weeklyTopic not in allClasses:
                #print 'Weekly topic not in all classes:', weeklyTopic
                continue

            d = os.path.join(target_dir,weeklyTopic)
            if not os.path.exists(d): os.makedirs(d)
            os.chdir(d)

            weekClasses = allClasses[weeklyTopic]
            classNames = weekClasses['classNames']

            for i,className in enumerate(classNames,start=1):
                if className not in weekClasses:
                    continue
                
                classResources = weekClasses[className]

                # the directory name is the class name but prefix it with a counter
                # so the chronological order of classes is not lost
                dirName = str(i).zfill(2) + " - " + className

                if not os.path.exists(dirName): os.makedirs(dirName)
                os.chdir(dirName)

                for classResource in classResources:
                    if not isValidURL(classResource):
                        absoluteURLGen = AbsoluteURLGen(course_url)
                        classResource = absoluteURLGen.get_absolute(classResource)
                        print classResource, ' - is not a valid url'

                        if not isValidURL(classResource):
                            print classResource, ' - is not a valid url'
                            continue

                    print 'Downloading resource - ', classResource
                    self.download(classResource, dirName)

                os.chdir('..')
            os.chdir('..')

    @staticmethod
    def extractFileName(contentDispositionString):
        #print contentDispositionString
        pattern = 'attachment; filename="(.*?)"'
        m = re.search(pattern, contentDispositionString)
        try:
            return m.group(1)
        except Exception:
            return ''

    @staticmethod
    def getFileName(header):
        try:
            return CourseraDownloader.extractFileName(header['Content-Disposition']).lstrip()
        except Exception:
            return '' 

    @staticmethod
    def isTextFile(fileName):
        splits = fileName.split('.')
        extension = splits[len(splits) - 1]
        if extension.lower() == 'txt':
            return True

        return False

    @staticmethod
    def getContentLength(header):
        try:
            return int(header['Content-Length'])
        except Exception:
            return 0 

    @staticmethod
    def isHtml(header):
        try:
            return header['Content-Type'] == 'text/html'
        except Exception:
            return False

    @staticmethod
    def getFileNameFromURL(url):
        splits = url.split('/')    
        splits.reverse()
        splits = urllib.unquote(splits[0])
        #Seeing slash in the unquoted fragment
        splits = splits.split('/')
        return splits[len(splits) - 1]

def sanitiseFileName(fileName):
    return re.sub('[:\?\\\\/]', '', fileName).strip()

def isValidURL(url):
    return url.startswith('http') or url.startswith('https')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download Coursera classes.')
    parser.add_argument("-u", dest='username', type=str, help='coursera username')
    parser.add_argument("-p", dest='password', type=str, help='coursera password')
    parser.add_argument("-d", dest='target_dir', type=str, default=".", help='destination directory')
    parser.add_argument('course_url', metavar='<course url or course name>', type=str, help='course url')
    args = parser.parse_args()

    d = CourseraDownloader(args.username,args.password)
    d.login()

    curl = args.course_url if args.course_url.startswith("http") else d.course_url_from_name(args.course_url)

    d.download_course(curl,dest_dir=args.target_dir)
