import re
import urllib
import argparse
import os
from mechanize import Browser
from bs4 import BeautifulSoup

class CourseraDownloader(object):
    """
    Class to download content (videos, lecture notes, ...) from coursera.org for
    use offline.

    Originally forked from: https://github.com/abhirama/coursera-download but
    heavily modified since.
    """

    HOME_URL = 'http://class.coursera.org/%s/class/index'
    LECTURE_URL = 'http://class.coursera.org/%s/lecture/index'
    LOGIN_URL ='http://class.coursera.org/%s/auth/auth_redirector?type=login&subtype=normal'

    def __init__(self,username,password):
        self.username = username
        self.password = password

        self.browser = Browser()
        self.browser.set_handle_robots(False)

    def login(self,course_name):
        print "* Authenticating..."

        # open the course login page
        page = self.browser.open(self.LOGIN_URL % course_name)

        # check if we are already logged in by checking for a password field
        bs = BeautifulSoup(page)
        pwdfield = bs.findAll("input",{"id":"password_login"})

        if pwdfield:
            self.browser.form = self.browser.forms().next()
            self.browser['email'] = self.username
            self.browser['password'] = self.password
            self.browser.submit()
        else:
            # no login form, already logged in
            print "* Already logged in"

    def course_name_from_url(self,course_url):
        """Given the course URL, return the name, e.g., algo2012-p2"""
        return course_url.split('/')[3]

    def lecture_url_from_name(self,course_name):
        """Given the name of a course, return the video lecture url"""
        return self.LECTURE_URL % course_name

    def get_downloadable_content(self,course_url):
        """Given the video lecture URL of the course, return a list of all
        downloadable resources."""

        print "* Collecting downloadable content from " + course_url

        # get the course name, and redirect to the course lecture page
        vidpage = self.browser.open(course_url)

        # extract the weekly classes
        soup = BeautifulSoup(vidpage)
        headers = soup.findAll("h3", { "class" : "list_header" })

        weeklyTopics = []
        allClasses = {}

        # for each weekly class
        for header in headers:
            ul = header.findNext('ul')
            sanitisedHeaderName = sanitiseFileName(header.text)
            weeklyTopics.append(sanitisedHeaderName)
            lis = ul.findAll('li')
            weekClasses = {}

            # for each lecture in a weekly class
            classNames = []
            for li in lis:
                className = sanitiseFileName(li.a.text)
                classNames.append(className)
                classResources = li.find('div', {'class': 'item_resource'})

                hrefs = classResources.findAll('a')

                resourceLinks = []

                # for each resource of that lecture (slides, pdf, ...)
                for href in hrefs:
                    #if href.find('i',{'class':'icon-info-sign'}):
                    #    # skip info links (e.g., to wikipedia, etc)
                    #    continue
                    resourceLinks.append(href['href'])

                weekClasses[className] = resourceLinks

            # keep track of the list of classNames in the order they appear in the html
            weekClasses['classNames'] = classNames

            allClasses[sanitisedHeaderName] = weekClasses

        return (weeklyTopics, allClasses)

    def download(self, url, folder):
        """Download the given url to the given folder"""
        r = self.browser.open(url)

        fileName = sanitiseFileName(CourseraDownloader.getFileName(r.info()))
        if not fileName:
            fileName = CourseraDownloader.getFileNameFromURL(url)

        if os.path.exists(fileName):
            print "    - already exists, skipping"
        else:
            self.browser.retrieve(url,fileName)

    def download_course(self,cname,dest_dir="."):
        """Download all the contents of the course to the given destination directory (defaults to .)"""

        # Ensure we are logged in
        self.login(cname)

        # get the lecture url
        course_url = self.lecture_url_from_name(cname)

        (weeklyTopics, allClasses) = self.get_downloadable_content(course_url)
        print '* Got all downloadable content for ' + cname

        target_dir = os.path.abspath(os.path.join(dest_dir,cname))
        print "* " + cname + " will be downloaded to " + target_dir

        for j,weeklyTopic in enumerate(weeklyTopics,start=1):
            if weeklyTopic not in allClasses:
                #print 'Weekly topic not in all classes:', weeklyTopic
                continue

            # ensure a numeric prefix in the week directory names to ensure
            # chronological ordering
            weekdir = str(j).zfill(2) + " - " + weeklyTopic
            d = os.path.join(target_dir,weekdir)
            if not os.path.exists(d): os.makedirs(d)
            os.chdir(d)

            weekClasses = allClasses[weeklyTopic]
            classNames = weekClasses['classNames']

            for i,className in enumerate(classNames,start=1):
                if className not in weekClasses:
                    continue

                classResources = weekClasses[className]

                # ensure chronological ordering of the classes within a week
                dirName = str(i).zfill(2) + " - " + className

                if not os.path.exists(dirName): os.makedirs(dirName)
                os.chdir(dirName)

                print "  - Downloading resources for " + className

                for classResource in classResources:
                    if not isValidURL(classResource):
                        absoluteURLGen = AbsoluteURLGen(course_url)
                        classResource = absoluteURLGen.get_absolute(classResource)
                        print "  -" + classResource, ' - is not a valid url'

                        if not isValidURL(classResource):
                            print "  -" + classResource, ' - is not a valid url'
                            continue

                    try:
                       #print '  - Downloading ', classResource
                       self.download(classResource, dirName)
                    except Exception as e:
                       print "    - failed: ",classResource,e

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
    def getFileNameFromURL(url):
        splits = url.split('/')
        splits.reverse()
        splits = urllib.unquote(splits[0])
        #Seeing slash in the unquoted fragment
        splits = splits.split('/')
        fname = splits[len(splits) - 1]

        # add an extension if none
        ext = os.path.splitext(fname)[1]
        if not ext: fname += ".html"

        return fname


def sanitiseFileName(fileName):
    return re.sub('[:\?\\\\/<>\*]', '', fileName).strip()

def isValidURL(url):
    return url.startswith('http') or url.startswith('https')

class AbsoluteURLGen(object):
    """
    Generate absolute URLs from relative ones
    Source: AbsoluteURLGen copy pasted from http://www.python-forum.org/pythonforum/viewtopic.php?f=5&t=12515
    """
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

if __name__ == '__main__':
    """Main function, call with -h for usage information"""

    # parse the commandline arguments
    parser = argparse.ArgumentParser(description='Download Coursera.org course videos/docs for offline use.')
    parser.add_argument("-u", dest='username', type=str, help='coursera.org username')
    parser.add_argument("-p", dest='password', type=str, help='coursera.org password')
    parser.add_argument("-d", dest='target_dir', type=str, default=".", help='destination directory where everything will be saved')
    parser.add_argument('course_names', nargs="+", metavar='<course name>',
                        type=str, help='one or more course names (from the url)')
    args = parser.parse_args()

    # instantiate the downloader class
    d = CourseraDownloader(args.username,args.password)

    # download the content
    for cn in args.course_names:
        d.download_course(cn,dest_dir=args.target_dir)

