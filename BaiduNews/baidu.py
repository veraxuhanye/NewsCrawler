#coding:utf-8
import re
import io
import sys
import os
import os.path
import urllib2
import httplib
import chardet
import csv
import time
import datetime
import requests
import socket
import logging
import pdfkit
import articleDateExtractor
import thulac
from bs4 import BeautifulSoup
from textrank4zh import TextRank4Keyword, TextRank4Sentence
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
#from xhtml2pdf import pisa

httplib.HTTPConnection._http_vsn = 10
httplib.HTTPConnection._http_vsn_str = 'HTTP/1.0'

'''
Ref:
基于 http://webcache.googleusercontent.com/search?q=cache:GCsJ6iNTfzoJ:www.lai18.com/content/1724530.html+&cd=10&hl=en&ct=clnk&gl=us
http://www.tqcto.com/article/code/286211.html
beautifulsoup: https://www.crummy.com/software/BeautifulSoup/bs4/doc.zh/
pdfkit: https://pypi.python.org/pypi/pdfkit
TextRank4ZH: https://github.com/letiantian/TextRank4ZH

'''

#function to generate pdfs
def generatePDF(weburl, filename):

    t = time.time()
    #driver for phantomJS
    #driver = webdriver.PhantomJS(service_args=['--ignore-ssl-errors=true', '--ssl-protocol=ANY'])
    driver.command_executor._commands['executePhantomScript'] = ('POST', '/session/$sessionId/phantom/execute')
    #driver.get(weburl)
    driver.set_page_load_timeout(10)
    try:
        driver.get(weburl)
    except TimeoutException:
        driver.execute_script("window.stop();")
        logging.debug("time out for loading web page")
    pageFormat = '''this.paperSize = {format: "A4", orientation: "portrait" };'''
    driver.execute('executePhantomScript', {'script': pageFormat, 'args' : [] })
    #execute(pageFormat, [])

    pdfpath = "/Users/hanyexu/Desktop/news/pdfs/%s.pdf"%(filename)

    render = '''this.render("%s")'''%(pdfpath)
    driver.execute('executePhantomScript', {'script': render, 'args' : [] })
    #execute(render, [])

#提取网页正文，放入txt中
def remove_js_css (content):
    """ remove the the javascript and the stylesheet and the comment content (<script>....</script> and <style>....</style> <!-- xxx -->) """
    r = re.compile(r'''<script.*?</script>''',re.I|re.M|re.S)
    s = r.sub ('',content)
    r = re.compile(r'''<style.*?</style>''',re.I|re.M|re.S)
    s = r.sub ('', s)
    r = re.compile(r'''<!--.*?-->''', re.I|re.M|re.S)
    s = r.sub('',s)
    r = re.compile(r'''<meta.*?>''', re.I|re.M|re.S)
    s = r.sub('',s)
    r = re.compile(r'''<ins.*?</ins>''', re.I|re.M|re.S)
    s = r.sub('',s)
    return s

def remove_empty_line (content):
    """remove multi space """
    r = re.compile(r'''^\s+$''', re.M|re.S)
    s = r.sub ('', content)
    r = re.compile(r'''\n+''',re.M|re.S)
    s = r.sub('\n',s)
    return s

def remove_any_tag (s):
    s = re.sub(r'''<[^>]+>''','',s)
    return s.strip()

def remove_any_tag_but_a (s):
    text = re.findall (r'''<a[^r][^>]*>(.*?)</a>''',s,re.I|re.S|re.S)
    text_b = remove_any_tag (s)
    return len(''.join(text)),len(text_b)

def remove_image (s,n=50):
    image = 'a' * n
    r = re.compile (r'''<img.*?>''',re.I|re.M|re.S)
    s = r.sub(image,s)
    return s

def remove_video (s,n=1000):
    video = 'a' * n
    r = re.compile (r'''<embed.*?>''',re.I|re.M|re.S)
    s = r.sub(video,s)
    return s

def sum_max (values):
    cur_max = values[0]
    glo_max = -999999
    left,right = 0,0
    for index,value in enumerate (values):
        cur_max += value
        if (cur_max > glo_max) :
            glo_max = cur_max
            right = index
        elif (cur_max < 0):
            cur_max = 0

    for i in range(right, -1, -1):
        glo_max -= values[i]
        if abs(glo_max < 0.00001):
            left = i
            break
    return left,right+1

def method_1 (content, k=1):
    if not content:
        return None,None,None,None
    tmp = content.split('\n')
    group_value = []
    for i in range(0,len(tmp),k):
        group = '\n'.join(tmp[i:i+k])
        group = remove_image (group)
        group = remove_video (group)
        text_a,text_b= remove_any_tag_but_a (group)
        temp = (text_b - text_a) - 8
        group_value.append (temp)
    left,right = sum_max (group_value)
    return left,right, len('\n'.join(tmp[:left])), len ('\n'.join(tmp[:right]))

def extract (content):
    content = remove_empty_line(remove_js_css(content))
    left,right,x,y = method_1 (content)
    return '\n'.join(content.split('\n')[left:right])

#输入url，将其新闻页的正文输入txt
def extract_news_content(web_url, csv_content):
    request = urllib2.Request(web_url)
    logging.debug(">>>Parse content")
    #在请求加上头信息，伪装成浏览器访问
    request.add_header('User-Agent','Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6')
    opener = urllib2.build_opener()
    try:
        html= opener.open(request, timeout=2).read()
    except urllib2.HTTPError, e:
        logging.debug('1.HTTPError = ' + str(e.code))
        return
    except urllib2.URLError, e:
        if isinstance(e.reason, socket.timeout):
            logging.debug("1.URLE timeout1")
        logging.debug('1.URLError = ' + str(e.reason))
        return
    except socket.timeout, e:
        logging.debug("1.URLE timeout2")
        return
    except Exception:
        import traceback
        logging.debug('1.generic exception: ' + traceback.format_exc())
        return

    infoencode = chardet.detect(html)['encoding']##通过第3方模块来自动提取网页的编码
    if html!=None and infoencode!=None:#提取内容不为空，error.或者用else
        html = html.decode(infoencode,'ignore')
        soup=BeautifulSoup(html,"html.parser")
        content=soup.renderContents()
        content=soup.prettify()
        content_text=extract(content)#提取新闻网页中的正文部分，化为无换行的一段文字
        content_text= re.sub(" "," ",content_text)
        #content_text= re.sub(">","",content_text)
        #content_text= re.sub(""",'""',content_text)
        content_text= re.sub("<[^>]*>","",content_text)
        content_text= re.sub("\n","",content_text)
        content_text= re.sub(" ","",content_text)
        content_text= re.sub("\t","",content_text)
        #print(content_text)

        #--- start analysis text---
        encodetext = content_text
        #tr4w.analyze(text=encodetext, lower=True, window=2)
        try:
            breakdowns = thu1.cut(encodetext, text=False)
        except:
            logging.debug("Error of extract locations")
            LString = ""
            csv_content.append(LString.encode("utf-8"))
            csv_content.append(content_text.encode("utf-8"))
            return

        LWords = set()
        for words in breakdowns:
            if len(words) == 2 and words[1] == 'ns':
                LWords.add(words[0])
        # for words in tr4w.words_no_stop_words:
        #     for word in words:
        #         if word in LocationDic:
        #             LWords.add(word)

        LString = "/".join(LWords)

        logging.debug(">>>Finished Parse content")

        csv_content.append(LString.encode("utf-8"))
        csv_content.append(content_text.encode("utf-8"))


def search(key_word, cateLabel, csv_name, rawmon, rawyear):

    cwd = os.getcwd() # get current path pwd
    open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword

    #--- write to current CSV---
    ftmp = open(csv_name,'a')
    writer=csv.writer(ftmp)

    #--- Inite search engine---
    search_url='http://news.baidu.com/ns?word=key_word&tn=news&from=news&cl=2&rn=20&ct=1'
    req =  urllib2.Request(search_url.replace('key_word',key_word))
    req.add_header('User-Agent','Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6')
    opener = urllib2.build_opener()
    try:
        html= opener.open(req).read()
        #req=urllib2.urlopen(search_url.replace('key_word',key_word))
        #req = urllib2.urlopen(search_url)
        #req = requests.get(search_url, headers=headers)
    except urllib2.HTTPError, e:
        logging.debug('2.HTTPError = ' + str(e.code))
        ftmp.close()
        open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword
        return
    except urllib2.URLError, e:
        if isinstance(e.reason, socket.timeout):
            logging.debug("2.URLE timeout1")
        logging.debug('2.URLError = ' + str(e.reason))
        ftmp.close()
        open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword
        return
    except socket.timeout, e:
        logging.debug("2.URLE timeout2")
        ftmp.close()
        open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword
        return
    except Exception:
        import traceback
        logging.debug('2.generic exception: ' + traceback.format_exc())
        ftmp.close()
        open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword
        return

    #--- start crawling ---
    logging.debug(">>>Search page Crawled")
    real_visited=0#已扒的txt数量
    for count in range(8):
        cntTR = 0 # a variable to count time range for every page
        if html == "":
            logging.debug("Error: Nothing in the HTML.")
            return
        #print(html)
        soup=BeautifulSoup(html,"html.parser")
        #content = soup.html.body.find_all('h3', {'class' : 'c-title'})
        #content  = soup.findAll('li', {'class': 'result'}) #resultset object
        content = soup.html.body.find_all('div', {'class' : 'result'})
        num = len(content)
        for i in range(num):
            csv_content=[] # initialization for cvs row
            #先解析出来所有新闻的标题、来源、时间、url
            p_str= content[i].find('a') #if no result then nontype object
            contenttitle=p_str.renderContents()
            contenttitle=contenttitle.decode('utf-8', 'ignore')#need it
            contenttitle= re.sub("<[^>]+>","",contenttitle)
            contentlink=str(p_str.get("href"))
            visited_url=open(r''+cwd+'/visited-cn.txt','r')
            visited_url_list=visited_url.readlines()
            visited_url.close()#及时close
            exist=0
            for item in visited_url_list:
                if contentlink==item:
                    exist=1
            if exist!=1:#如果未被访问url
                p_str2= content[i].find('p').renderContents()
                #print(p_str2)
                contentauthor=p_str2[:p_str2.find('  ')]#来源
                contentauthor=contentauthor.decode('utf-8', 'ignore')#时
                contenttime=p_str2[p_str2.find('  ')+len('  '):]
                if "小时前" in contenttime:
                    contenttime = datetime.datetime.now().strftime("%Y年%m月%d日")
                if "年" in contenttime and "月" in contenttime:
                    yearnum = contenttime.split("年")[0]
                    monthnum = contenttime.split("年")[1].split("月")[0]
                    if int(yearnum) < 2000 and rawyear in p_str2:
                        yearnum = rawyear
                    elif int(yearnum) < 2000 or int(monthnum) > 12 or int(monthnum) < 1:
                        logging.debug("time format error"+p_str2)
                        continue
                else:
                    logging.debug("time format error"+ p_str2)
                    continue

                logging.debug("News from "+p_str2)

                #--- check time range ----
                if yearnum == rawyear and int(monthnum) > int(rawmon):
                    continue #skip bigger month
                elif yearnum != rawyear or monthnum != rawmon:
                    cntTR += 1
                    # if cntTR == 5:
                    #     open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword
                    #     logging.debug(">>>Articles are out of time Range")
                    #     break
                    continue


                contenttime=contenttime.decode('utf-8', 'ignore')
                real_visited+=1

                #---save to csv----
                csv_content.append(real_visited)
                csv_content.append(cateLabel.encode("utf-8"))
                csv_content.append(urllib2.unquote(key_word))
                csv_content.append(contenttitle.encode("utf-8"))
                csv_content.append(contentauthor.encode("utf-8"))
                csv_content.append(contenttime.encode("utf-8"))
                csv_content.append(contentlink)

                # #save pdf --- TODO: might need later
                # options = {
                #     'quiet': '',
                #     'no-background': '',
                #     'disable-external-links':'',
                #     'disable-forms': '',
                #     'no-images': '',
                #     'disable-internal-links': '',
                #     'load-error-handling':'skip',
                #     'disable-local-file-access':''
                # }
                # pdf_name=r"/Users/hanyexu/Desktop/news/pdfs/%s_%d.pdf"%(urllib2.unquote(key_word),real_visited)
                # try:
                #     pdfkit.from_url(contentlink, pdf_name,options=options)
                #     #pdfkit.from_url('baidu.com', 'out.pdf')
                # except Exception:
                #     print("wkhtmltopdf Exception!")

                # save pdf use PhantomJS
                #pdfname = "%s_%d"%(urllib2.unquote(key_word),real_visited)
                #generatePDF(contentlink, pdfname)

                # --- extract the news content
                extract_news_content(contentlink,csv_content)#还写入文件
                visited_url_list.append(contentlink)#访问之
                visited_url=open(r''+cwd+'/visited-cn.txt','a')#标记为已访问，永久存防止程序停止后丢失
                visited_url.write(contentlink+u'\n')
                visited_url.close()

                # --- write to csv ---
                writer.writerow(csv_content)

                logging.debug( '%s - %d' % (urllib2.unquote(key_word),real_visited))

            if real_visited >=100:
                logging.debug(">>>100 articles visited.")
                break
            #解析下一页
        if real_visited >=100:
            logging.debug(">>>100 articles visited.break.")
            break
        if count==0:
            next_num=0
        else:
            next_num=1
        try:
            next_page='http://news.baidu.com'+soup('a',{'href':True,'class':'n'})[next_num]['href'] # search for the next page
        except IndexError:
            logging.debug("no next page!!!")
            return
        #print next_page
        logging.debug(">>>Parse next page.")

        req =  urllib2.Request(next_page)
        req.add_header('User-Agent','Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6')
        opener = urllib2.build_opener()
        try:
            html= opener.open(req).read()
        except urllib2.HTTPError, e:
            logging.debug('3.HTTPError = ' + str(e.code))
            ftmp.close()
            open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword
            return
        except urllib2.URLError, e:
            if isinstance(e.reason, socket.timeout):
                logging.debug("3.URLE timeout1")
            logging.debug('3.URLError = ' + str(e.reason))
            ftmp.close()
            open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword
            return
        except socket.timeout, e:
            logging.debug("3.URLE timeout2")
            ftmp.close()
            open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword
            return
        except Exception:
            import traceback
            logging.debug('3.generic exception: ' + traceback.format_exc())
            ftmp.close()
            open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword
            return

    logging.debug(">>>Finished current searching word.")
    #--- check if this keyword has no record---
    if real_visited < 5:
        fback= open(r""+os.getcwd()+r"/Backup/KeywordsBackup.txt",'a')
        fback.write(urllib2.unquote(key_word+"\n").encode('utf-8'))
        fback.close()
    ftmp.close()
    open(r''+cwd+'/visited-cn.txt','w').close() # reset the visited link for a new keyword


if __name__=='__main__':

    print('>>>Start searching for news from news.baidu.com. Please make sure the directory is correct for storage.')
    rawdate = raw_input('Please input date you want to search (Format mm-yyyy):\n')
    while rawdate == "":
        rawdate = raw_input('Invalid! Input date you want to search (Format mm-yyyy):\n')
    rawmon = rawdate.split("-")[0]
    rawyear = rawdate.split("-")[1]

    #--- init the csv file ---
    cwd = os.getcwd() # get current path pwd
    csv_name=r"" + cwd + r"/CSV/Baidu-"+rawdate+".csv"
    print(">>>Initial CSV file for storage, file name is: " + csv_name)

    if os.path.exists(csv_name):
        print("File already exists, Do you want to override it?\n")
        rawans = raw_input('Yes/No\n')
        if rawans == 'Yes':
            os.remove(csv_name)
        elif rawans == 'No':
            print("Program Exit. Please run the script again.")
            sys.exit()
        else:
            print("Unknown response. Program Exit.")
            sys.exit()
    #--- clean back up file ---
    fback= open(r""+os.getcwd()+r"/Backup/KeywordsBackup.txt",'w').close()

    ftmp = open(csv_name,'wb')
    ftmp.write('\xEF\xBB\xBF') # must include this for chinese
    writer=csv.writer(ftmp)
    csv_header=[]
    csv_header.append('Number')
    csv_header.append('Category')
    csv_header.append('Keyword')
    csv_header.append('title')
    csv_header.append('author')
    csv_header.append('time')
    csv_header.append('url')
    csv_header.append('locations')
    csv_header.append('context')
    writer.writerow(csv_header)
    ftmp.close()

    #---build a dictionary for provinces and cities --- TODO: not use now for NLP lib
    # LocationDic = {}
    # ltmp = open('./LName', 'r')
    # lname = ltmp.readline().rstrip().decode('utf-8')
    # while(lname):
    #     LocationDic[lname] = 1
    #     lname = ltmp.readline().rstrip().decode('utf-8')
    # ltmp.close()
    #---------------------------------------------------

    print(">>>Initial NLP settings")
    thu1 = thulac.thulac()

    raw_word=raw_input('Please input a key word, or use ENTER to load default keywords list:\n') #get the keyword from type in

    #--- driver for PDF generator ----
    #driver = webdriver.PhantomJS(service_args=['--ignore-ssl-errors=true', '--ssl-protocol=ANY']) #for pdf generation
    #---------------------------------

    #--- NLP libarary -- TODO: not working since 01/2017
    #tr4w = TextRank4Keyword() #for text NLP analysis
    #-------------------

    #initial log #
    logfn = r"" + os.getcwd() + r"/Logs/" +datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")+".log"
    logging.basicConfig(filename=logfn, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    print("Start the program")

    #--- Load default keyword list ---
    if(raw_word == ""):
        logging.debug("Loading default keywords")
        keywords = open('./keywords', 'r')
        keyword = keywords.readline().rstrip()
        while(keyword):
            if keyword == "General":
                cateLabel = "General"
                keyword = keywords.readline().rstrip()
                continue
            elif keyword == "Buddhism":
                cateLabel = "Buddhism"
                keyword = keywords.readline().rstrip()
                continue
            elif keyword == "Islam":
                cateLabel = "Islam"
                keyword = keywords.readline().rstrip()
                continue
            elif keyword == "Daoism":
                cateLabel = "Daoism"
                keyword = keywords.readline().rstrip()
                continue
            elif keyword == "Christianity":
                cateLabel = "Christianity"
                keyword = keywords.readline().rstrip()
                continue
            elif keyword == "Confucian":
                cateLabel = "Confucian"
                keyword = keywords.readline().rstrip()
                continue
            elif keyword == "Black":
                cateLabel = "Black"
                keyword = keywords.readline().rstrip()
                continue
            elif keyword == "":
                keyword = keywords.readline().rstrip()
                continue

            logging.debug(">>>Searching for keyword: " + keyword)
            key_word=urllib2.quote(keyword)
            search(key_word, cateLabel, csv_name, rawmon, rawyear)
            logging.debug(">>>Finished this keyword ")
            keyword = keywords.readline().rstrip()
        keywords.close()
    #--- Serach for inputed keywords---
    else:
        logging.debug(">>>search for customized word")
        key_word=urllib2.quote(raw_word)
        cateLabel = "Unknown"
        search(key_word, cateLabel, csv_name,rawmon, rawyear)

    print("Finish Crawling news from news.baidu.com.")