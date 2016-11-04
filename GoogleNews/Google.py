# encoding:utf-8
# author -- Hanye Xu
import re
import urllib2
import gnp
import csv
import chardet
import pdfkit
import articleDateExtractor
from bs4 import BeautifulSoup
from selenium import webdriver
import codecs
import json

'''
used gnp api for google news crawler
Please install gnp 0.0.4 first
Ref: http://mpand.github.io/gnp/
Ref: https://github.com/Webhose/article-date-extractor
'''

# used for generating pdf for each url
#execute function for phantomJS
# def execute(script, args):
#     driver.execute('executePhantomScript', {'script': script, 'args' : args })

#function to generate pdfs
def generatePDF(weburl, filename):
    #driver for phantomJS
    driver = webdriver.PhantomJS('phantomjs')
    driver.command_executor._commands['executePhantomScript'] = ('POST', '/session/$sessionId/phantom/execute')
    driver.get(weburl)
    pageFormat = '''this.paperSize = {format: "A4", orientation: "portrait" };'''
    driver.execute('executePhantomScript', {'script': pageFormat, 'args' : [] })
    #execute(pageFormat, [])

    pdfpath = "/Users/hanyexu/Desktop/newsgoo/pdfs/%d.pdf"%(filename)

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

    #在请求加上头信息，伪装成浏览器访问
    request.add_header('User-Agent','Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.1.6) Gecko/20091201 Firefox/3.5.6')
    opener = urllib2.build_opener()
    try:
        html= opener.open(request).read()
    except urllib2.HTTPError, e:
        print('HTTPError = ' + str(e.code))
        return
    except urllib2.URLError, e:
        print('URLError = ' + str(e.reason))
        return
    except Exception:
        import traceback
        print('generic exception: ' + traceback.format_exc())
        return

    infoencode = chardet.detect(html)['encoding']##通过第3方模块来自动提取网页的编码
    if html!=None and infoencode!=None:#提取内容不为空，error.或者用else
        html = html.decode(infoencode,'ignore')
        soup=BeautifulSoup(html,"html.parser")
        for i in soup.findAll(re.compile('Published')):
            print(i)
        content=soup.renderContents()
        content=soup.prettify()
        content_text=extract(content)#提取新闻网页中的正文部分，化为无换行的一段文字
        content_text= re.sub(" "," ",content_text)
        #content_text= re.sub(">","",content_text)
        #content_text= re.sub(""",'""',content_text)
        content_text= re.sub("<[^>]*>","",content_text)
        content_text= re.sub("\n","",content_text)
        content_text= re.sub("  ","",content_text)
        print(content_text)
        # file = open(file_name,'a')#append
        # file.write(content_text.encode('utf-8'))
        # file.close()

        csv_content.append(content_text.encode("utf-8"))

def search(key_word):

    #setting up the csv file
    csv_name=r"/Users/hanyexu/Desktop/newsgoo/rst.csv"
    ftmp = open(csv_name,'wb')
    ftmp.write('\xEF\xBB\xBF')
    writer=csv.writer(ftmp)
    csv_header=[]
    csv_header.append('title')
    csv_header.append('author')
    csv_header.append('time')
    csv_header.append('url')
    csv_header.append('context')
    writer.writerow(csv_header)

    jresult = gnp.get_google_news_query(key_word) # jresult is inform of json
    test = jresult['stories']
    nums = len(test)
    for i in range(nums):
        csv_content=[] # initialization for cvs row
        item = test[i]
        contenttitle=item['title']
        contenttitle=contenttitle.decode('utf-8', 'ignore')
        contentauthor=item['source']
        contentauthor=contentauthor.decode('utf-8', 'ignore')
        contentlink=item['link']
        content=item['content_snippet']
        content=content.decode('utf-8', 'ignore')

        #get the article time
        contenttime = articleDateExtractor.extractArticlePublishedDate(contentlink)

        # save to csv
        csv_content.append(contenttitle.encode("utf-8"))
        csv_content.append(contentauthor.encode("utf-8"))
        csv_content.append(contenttime)
        csv_content.append(contentlink)
        #csv_content.append(content.encode("utf-8"))

        extract_news_content(contentlink,csv_content)#还写入文件

        # #save pdf
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
        # pdf_name=r"/Users/hanyexu/Desktop/newsgoo/pdfs/%d.pdf"%(i+1)
        # try:
        #     pdfkit.from_url(contentlink, pdf_name,options=options)
        #     #pdfkit.from_url('baidu.com', 'out.pdf')
        # except Exception:
        #     print("wkhtmltopdf Exception!")

        #save pdf
        generatePDF(contentlink, i+1)

        writer.writerow(csv_content)

    ftmp.close()

if __name__=='__main__':
    print('Start search for news from news.google.com. Please make sure the directory is correct for storage.')
    raw_word=raw_input('input key word:')
    key_word=urllib2.quote(raw_word)
    search(key_word)
