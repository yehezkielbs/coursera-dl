import re
import urllib
import argparse
import os
import errno
from mechanize import Browser
from bs4 import BeautifulSoup

class CourseraDownloader(object):
    """
    Class to download content (videos, lecture notes, ...) from coursera.org for
    use offline.

    https://github.com/dgorissen/coursera-dl
    """

    BASE_URL =    'http://class.coursera.org/%s'
    HOME_URL =    BASE_URL + '/class/index'
    LECTURE_URL = BASE_URL + '/lecture/index'
    LOGIN_URL =   BASE_URL + '/auth/auth_redirector?type=login&subtype=normal'
    QUIZ_URL =    BASE_URL + '/quiz/index'

    def __init__(self,username,password):
        self.username = username
        self.password = password

        self.browser = Browser()
        self.browser.set_handle_robots(False)

    def login(self,course_name):
        print "* Authenticating as %s..." % self.username

        # open the course login page
        page = self.browser.open(self.LOGIN_URL % course_name)

        # check if we are already logged in by checking for a password field
        bs = BeautifulSoup(page)
        pwdfield = bs.findAll("input",{"id":"password_login"})

        if pwdfield:
            self.browser.form = self.browser.forms().next()
            self.browser['email'] = self.username
            self.browser['password'] = self.password
            r = self.browser.submit()

            # check that authentication actually succeeded
            bs2 = BeautifulSoup(r.read())
            title = bs2.title.string
            if title.find("Login Failed") > 0:
                raise Exception("Failed to authenticate as %s" % (self.username,))
 
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

        cname = self.course_name_from_url(course_url)

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
                    resourceLinks.append( (href['href'],None) )
 
                # check if the video is included in the resources, if not download it separately 
                hasvid = [x for x,_ in resourceLinks if x.find('.mp4') > 0]
                if not hasvid:
                    ll = li.find('a',{'class':'lecture-link'})
                    lurl = ll['data-lecture-view-link']
                    p = self.browser.open(lurl)
                    bb = BeautifulSoup(p)
                    vurl = bb.find('source',type="video/mp4")['src']
                    # build the matching filename
                    fn = className + ".mp4"
                    resourceLinks.append( (vurl,fn) )
                     
                weekClasses[className] = resourceLinks
                  
            # keep track of the list of classNames in the order they appear in the html
            weekClasses['classNames'] = classNames

            allClasses[sanitisedHeaderName] = weekClasses

        return (weeklyTopics, allClasses)

    def download(self, url, target_fname=None):
        """Download the url to the given filename"""
        r = self.browser.open(url)
        
        # get the headers
        headers = r.info()

        # get the content length (if present)
        clen = int(headers['Content-Length']) if 'Content-Length' in headers else -1 
 
        # the absolute path
        filepath = target_fname or sanitiseFileName(CourseraDownloader.getFileName(headers))
        if not filepath:
            filepath = CourseraDownloader.getFileNameFromURL(url)

        # get just the filename        
        fname = os.path.split(filepath)[1]

        dl = True
        if os.path.exists(filepath):
            if clen > 0: 
                fs = os.path.getsize(filepath)
                delta = clen - fs

                # all we know is that the current filesize may be shorter than it should be and the content length may be incorrect
                # overwrite the file if the reported content length is bigger than what we have already by at least k bytes (arbitrary)

                # TODO this is still not foolproof as the fundamental problem is that the content length cannot be trusted
                # so this really needs to be avoided and replaced by something else, eg., explicitly storing what downloaded correctly
                if delta > 2:
                    print '    - "%s" seems incomplete, downloading again' % fname
                else:
            	    print '    - "%s" already exists, skipping' % fname
                    dl = False
            else:
                # missing or invalid content length
                # assume all is ok...
                dl = False

        try:
            if dl: self.browser.retrieve(url,filepath)
        except Exception as e:
            print "Failed to download url %s to %s: %s" % (url,filepath,e)

    def download_course(self,cname,dest_dir="."):
        """Download all the contents (quizzes, videos, lecture notes, ...) of the course to the given destination directory (defaults to .)"""

        # Ensure we are logged in
        self.login(cname)

        # get the lecture url
        course_url = self.lecture_url_from_name(cname)

        (weeklyTopics, allClasses) = self.get_downloadable_content(course_url)
        print '* Got all downloadable content for ' + cname
    
        target_dir = os.path.abspath(os.path.join(dest_dir,cname))
        
        # ensure the target dir exists
        if not os.path.exists(target_dir):
            os.mkdir(target_dir)
    
        print "* " + cname + " will be downloaded to " + target_dir

        # ensure the target directory exists
        if not os.path.exists(target_dir): os.makedirs(target_dir)
        	       
        # download the standard pages
        print "  - Downloading lecture/syllabus pages"
        self.download(self.HOME_URL % cname,target_fname=os.path.join(target_dir,"index.html"))
        self.download(course_url,target_fname=os.path.join(target_dir,"lectures.html"))
	#self.download((self.BASE_URL + '/wiki/view?page=syllabus') % cname, target_fname=os.path.join(target_dir,"syllabus.html"))
        
        # download the quizzes & homeworks
        #for qt in ['quiz','homework']:
        #    print "  - Downloading the '%s' quizzes" % qt
        #    try:
        #        self.download_quizzes(cname,target_dir,quiz_type=qt)
        #    except Exception as e:
        #        print "  - Failed %s" % e

        # now download the actual content (video's, lecture notes, ...)
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

                for classResource,tfname in classResources:
                    if not isValidURL(classResource):
                        absoluteURLGen = AbsoluteURLGen(course_url)
                        classResource = absoluteURLGen.get_absolute(classResource)
                        print "  -" + classResource, ' - is not a valid url'

                        if not isValidURL(classResource):
                            print "  -" + classResource, ' - is not a valid url'
                            continue

                    try:
                       #print '  - Downloading ', classResource
                       self.download(classResource,target_fname=tfname)
                    except Exception as e:
                       print "    - failed: ",classResource,e

                os.chdir('..')
            os.chdir('..')

    def download_quizzes(self,course,target_dir,quiz_type="quiz"):
        """Download each of the quizzes as separate html files, the quiz type is
        typically quiz or homework"""

        # extract the list of all quizzes
        qurl = (self.QUIZ_URL + "?quiz_type=" + quiz_type) % course
        p = self.browser.open(qurl)
        bs = BeautifulSoup(p)

        qlist = bs.find('div',{'class':'item_list'})
        qurls = [q['href'].replace('/start?','/attempt?') for q in qlist.findAll('a',{'class':'btn primary'})]
        titles = [t.string for t in qlist.findAll('h4')]

        # ensure the target directory exists
        dir = os.path.join(target_dir,quiz_type)

        try:
            os.makedirs(dir)
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else: raise

        # download each one
        for i,it in enumerate(zip(qurls,titles),start=1):
            q,t = it
            fname = os.path.join(dir,str(i).zfill(2) + " - " + sanitiseFileName(t) + ".html")
            if os.path.exists(fname):
                pass
                #print "  - already exists, skipping"
            else:
                self.browser.retrieve(q,fname)

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
    return re.sub('[:\?\\\\/<>\*"]', '', fileName.encode('ascii','ignore')).strip()

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

def main():
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

if __name__ == '__main__':
    main()
