#!/usr/bin/python
import datetime
import xmlrpclib
import re
import sys
import shutil
from optparse import OptionParser
from subprocess import call
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

from django.template import Template,Context

usage = " %prog [options] Results directory, html output directory"
parser = OptionParser(usage=usage)
parser.add_option("-a","--assembly", dest = "assembly", 
                action="store_true",
                help="Indicate that there is an assebly to report")
parser.add_option("-p","--project", type="int",
                dest="project", help="Specify the project ID from the lims")
parser.add_option("-u","--user", type="string",
                dest="username", help="Specify the username")
parser.add_option("-s","--password", type="string",
                dest="password", help="Specify the password")
(options, args) = parser.parse_args()
if len(args) != 2:
    print "Need results directory and html output directory"
    parser.print_help()
    sys.exit()
if options.project == None:
    print "Need project id (-p)"
    parser.print_help()
    sys.exit()
    
resultDir = args[0]
outputDir = args[1]
if os.path.exists(outputDir) == True:
    print "output directory already exists!!!!"
else:
    os.mkdir(outputDir)
    htaccess = open(outputDir+"/.htaccess", 'w')
    htaccess.write('AuthUserFile %s/.htpasswd \n' % (outputDir,))
    htaccess.write('AuthType Basic\n')
    htaccess.write('AuthName "Results"\n')
    htaccess.write('Require valid-user\n')
    htaccess.close()
    htpass = open(outputDir+"/.htpasswd", 'w')
    htpass.write('tbair:pGYk1xV5O9l2.\n')
    htpass.close()
    call (['htpasswd','-b',outputDir+"/.htpasswd",options.username,options.password])
if os.path.exists(resultDir) == False:
    print "result directory does not exist!!!!"
    sys.exit()


htmlRoot = '/var/www/html'
sys.path.append('/home/tbair')
url = 'http://dna-11.int-med.uiowa.edu/454/?q=services/xmlrpc'
url = 'http://dnacorevirt.healthcare.uiowa.edu:8080/454/?q=services/xmlrpc'
api = '28c3d63a8461d6fc6eaf117064195548'
drupal = xmlrpclib.ServerProxy(url)
connection = drupal.system.connect(api)
localDrupalDir = "/mnt/data_store/454_files/"
lgin = drupal.user.login(api,connection['sessid'],'tbair','*gaattc#')

def modifyPath(input):
    base = os.path.basename(input)
    modInput = os.path.join(localDrupalDir, base)
    new = os.path.join(outputDir,base)
    try:
        shutil.copy (modInput, new)
    except:
        print "not found %s" %(modInput,)
    new = new.replace (htmlRoot,"")
    return new

def loadTemplate():
    fp = open ('/opt/pageGen/output.html')
    t = Template(fp.read())
    fp.close()
    return t

def getIdProject(title):
    id = drupal.views.getView(api,lgin['sessid'],'specific_project',[],[title])
    return id

def getInfoProject(pid,type):
    info = drupal.views.getView(api,lgin['sessid'],type,[],[int(pid)])
    summary = []
    for i in info:
        temp = {}
        temp['title'] = i['title']
        temp['body'] = i['body']
        if len(i['files']) > 0:
            temp['file'] = []
            for f in i['files']:
                t = {}
                t['filepath'] = modifyPath(i['files'][f]['filepath'])
                t['filename'] = i['files'][f]['filename']
                t['filemime'] = i['files'][f]['filemime']
                temp['file'].append(t.copy())
        summary.append(temp.copy())
    return summary

def linkResults(results):
    #make a symlink from the web directory to the results return the symlink path
    newPath = os.path.join(outputDir,"results")
    print "linking %s to %s" %(newPath, results)
    #newPath = "./results"
    try:
        os.symlink(results,newPath)
    except Exception, e:
        print "Error symlinking %s %s" % (e,newPath)
    newPath = newPath.replace (htmlRoot,"")
    return newPath

def getFile(filename,dir):
    ret = []
    files = os.walk(dir)
    for f in files:
        for a in f[2]:
            if a == filename:
                ret.append(os.path.join(f[0],a))
    return ret

def detailResults(results):
    matchHash = {'aveContig':'avgContigSize\s+=\s+(\d+)',
        'largestContig':'largestContigSize\s+=\s+(\d+)',
        'Q40Base':'Q40PlusBases\s+=\s+(\d+),\s+\d+',
        'Q40percent':'Q40PlusBases\s+=\s+\d+,\s+(\d+)',
        }
    metricsFiles = getFile('454NewblerMetrics.txt',results)
    summary = []

    for m in metricsFiles:
        temp = {}
        #get the result directory name
        dir = os.path.dirname(m)
        temp['resFileName'] = os.path.basename(dir)
        mf = open (m).read()
        for mh in matchHash:
            res = re.search(matchHash[mh],mf)
            temp[mh] = res.group(1)
        summary.append(temp.copy())
    return summary

def detailRun(results):
    runFiles = getFile('454BaseCallerMetrics.txt', results)
    for r in runFiles:
        rkey = re.compile("""regionKey\n({\n\s+region = (\d+);.*)""")
        rf = open(r).read()
        regions = rkey.findall(rf)

results = {}

id = getIdProject(options.project)
results['title'] = 'NGS Sequencing Results'
results['description'] = ""
for i in id:
    results['description'] += i['title']
#results['resultDir'] = linkResults(resultDir)
linkResults(resultDir)
results['resultDir'] = './results'
if options.assembly == True:
    results['summary'] = detailResults(resultDir)
results['regions'] = detailRun(resultDir)
results['detail'] = ""
results['data'] = []
results['library'] = []
results['file'] = []
for i in id:
    if len(i['files']) > 0:
        for f in i['files']:
            t = {}
            t['filepath'] = modifyPath(i['files'][f]['filepath'])
            t['filename'] = i['files'][f]['filename']
            t['filemime'] = i['files'][f]['filemime']
            results['file'].append(t.copy())
for i in id:
    results['detail'] += i['body']
    results['data'].append(getInfoProject(i['nid'],'project_data'))
    results['library'].append(getInfoProject(i['nid'],'project_library'))
t = loadTemplate()
html = t.render(Context(results))
output = open (os.path.join(outputDir,"index.html"),'w')
#print html
output.write( html )
output.close()
print "INFO\t%s\t%s\thttp://dnacore454.healthcare.uiowa.edu/%s" % (options.username,options.password,os.path.basename(outputDir),)
