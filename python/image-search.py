import sys
import os

from os.path import splitext

from pathvalidate import sanitize_filename
import random
import requests
import traceback
import json

from urllib.parse import urlparse
from urllib.parse import unquote
from urllib.parse import parse_qs

import PIL
from PIL import Image
from PIL import UnidentifiedImageError

import base64
from io import StringIO, BytesIO

import lxml
import lxml.html
import cssselect

import re
import yaml

import time
from pprint import pprint


#-pip install webdriver-manager
#-pip install opencv

save_path = sys.argv[1]

use_thumbnails=False
if len(sys.argv) == 3 :
    if sys.argv[2].lower() == 'use_thumbnails':
        use_thumbnails=True

search_term = "random stuff"
#min_width=1024
#min_height=1024
num_images=50
num_columns=4
search_engine="Bing"

input_image_list=[]
output_image_list=[]
driver_path="./chromedriver_win32/chromedriver.exe"

selected_label=None
selected_index=None

DEBUG_ON=True
TRACE_ON=True


# Monkey patch to speed up gallery images
# https://github.com/gradio-app/gradio/issues/2635

#import numpy as np
#import cv2
#from cv2 import imencode
#import base64

#def encode_pil_to_base64_new(pil_image):
#    print("using new encoding method")
#    image_arr = np.asarray(pil_image)[:,:,::-1]
#    _, byte_data = imencode('.png', image_arr)        
#    base64_data = base64.b64encode(byte_data)
#    base64_string_opencv = base64_data.decode("utf-8")
#    return "data:image/png;base64," + base64_string_opencv
    
#end monkey patch    
    

def DEBUG_DUMP(x):
    print("---------BEGIN DEBUG---------------")
    pprint(vars(x))
    print("---------END DEBUG-----------------")
 
def DEBUG_ARRAY(x):
    print("---------BEGIN DEBUG ARRAY---------------")
    for e in x: print("DEBUG >>",e)
    print("---------END DEBUG ARRAY---------------")
 
 
def DEBUG(x):
    if DEBUG_ON: print("DEBUG",x)
      
def TRACE_IN(x):
    if TRACE_ON: print("TRACE: Entering",x)
      
def TRACE_OUT(x):
    if TRACE_ON: print("TRACE: Leaving",x)
    
def TRACE(x):
    if TRACE_ON: print("TRACE:",x)

def ERROR(x):
    print("ERROR:",x)   
    
#DEBUG("Thumbnail Test")  
#DEBUG(use_thumbnails)  
  
import gradio as gr
#apply monkey patch
#gr.processing_utils.encode_pil_to_base64 = encode_pil_to_base64_new 

with gr.Blocks() as selector:
  
    def search_str(x):
        s1=sanitize_filename(x)       
        s1=' '.join(s1.split()).replace(' ','+')
        return s1
  
    def chrome_driver():   
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--ignore-certificate-errors')

        driver = webdriver.Chrome(
            options=options,
            service=ChromeService(ChromeDriverManager().install())
        )
        return driver
        

    def get_html(url):
        #TRACE_IN("get_url")
        headers = {'User-Agent': user_agent_string()}             
        rsp=requests.get(url,headers=headers)
        tree = lxml.html.fromstring(rsp.content)
        
        #TRACE_OUT("get_url")
        return tree
        
        
    def extract_urls_from_google_script(page):
        #TRACE_IN("extract_images_from_google_script")
        elems=page.cssselect("script[nonce]") 
        tkn='AF_initDataCallback'
        n=len(tkn)    
        results={}
        
        s=[]
        for x in elems: 
            txt=""            
            txt=x.text_content()
            if txt[0:n] == tkn: 
                s.append(txt) 
        #there should be 2, so use the second        
     
        xarr=re.findall('\"444383007\":(\[.*?\])\}\]\]',s[1])         
        tst=xarr[0]
        tst_x=re.search('\"444383007\":(.*)',tst).group(1)
        
        if tst_x:xarr[0]=tst_x
        for x1 in xarr:
                   
            key=re.search('\"(.*?)\"',x1).group(1)
            harr=re.findall('\"(https:\/\/.*?)\"',x1)     
            
            if len(harr) < 3 : continue
            if len(key) != 14 : continue
              
            for idx,h in enumerate(harr):
                harr[idx]=h.encode().decode('unicode-escape')
            
            results[key]={}
            results[key]['turl']=harr[0]
            results[key]['murl']=harr[1]
            
            #DEBUG(results)

        #TRACE_OUT("extract_images_from_google_script")
        return results
        
        
        
        
        
    def get_google_images():
        #TRACE_IN("get_google_images")
        global search_term
        global num_images
        count=0;
        google_url=f"https://www.google.com/search?q={search_str(search_term)}&tbm=isch&tbs=isz:l"
                
        page=get_html(google_url)       
        urls=extract_urls_from_google_script(page)
                      
        image_data=[]
            
        try:
            elems=page.cssselect(".PNCib.MSM1fd.BUooTd") 
            for x in elems:
                xid=x.attrib["data-id"]
                data={
                        'img':None,
                        'turl':urls[xid]['turl'], 
                        'murl':urls[xid]['murl']      
                     }
                     
                image_data.append(data)
                count=count+1              
                if count == num_images: break            
               
        except Exception:
            traceback.print_exc()       
         
        #DEBUG(image_data)      
        #TRACE_OUT("get_google_images")
        return image_data

   
    def get_bing_images(): 
        #TRACE_IN("get_bing_images")
    
        global search_term
        global num_images
        count=0;
        
        bing_url=f"https://www.bing.com/images/search?q={search_str(search_term)}&first=1&qft=+filterui%3Aimagesize-wallpaper"                      
        page=get_html(bing_url)       
             
        #DEBUG(bing_url)
       
        image_data=[]
            
        try:
            
            elems=page.cssselect(".iusc") 
            
            delay=5 #secs 
            dt=0.25 #sec
            N=int(delay/dt)
                    
            for x1 in elems:
                mref=None;               
                mref=x1.attrib['m']
 
               # n=0
             #   while not mref:
               #     time.sleep(dt)
                 #   n=n+1
                #    if n > N: break
                #mref=x1.get_attribute('m')                  
                          
                if mref:
                    x=json.loads(mref)
                    #DEBUG(x)
                    data={
                        'timg':None,
                        'turl':x['turl'],
                        'murl':x['murl']
                      }
                                         
                    image_data.append(data)
                    count=count+1
                    #DEBUG(count)
                    if count == num_images: break
                                    
        except Exception:
            traceback.print_exc()       
         
        #DEBUG(image_data)     
        #TRACE_OUT("get_bing_images")        
        return image_data    
        
        
    def user_agent_string():
        agents=[
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",    
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5.2 Safari/605.1.1",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188"]
        n=len(agents)-1      
        return agents[random.randint(0,n)]
        
        
    def get_web_images(): 
        if search_engine == 'Google':
            return get_google_images()
        else:
            return get_bing_images()
           

    def extract_input_images(x1):
        #TRACE_IN("extract_input_images")
        global use_thumbnails
              
        images=[]
 
        for x in x1:      
           
            if use_thumbnails :      
                img_url=x['turl']
            else: 
                img_url=x['murl']
                       
            if img_url[:5] =="data:":
                n=img_url.find(',')+1
                b64s=img_url[n:]
                data=base64.b64decode(b64s)        
            else:
                headers = {'User-Agent': user_agent_string()}
                rsp=requests.get(img_url,headers=headers)
                data=rsp.content
            
            try:
                x['img']=Image.open(BytesIO(data))
            except PIL.UnidentifiedImageError:
                continue
                
            images.append(x)  
                      
        #TRACE_OUT("extract_input_images")        
        return images         
       
    def load_images():
        #TRACE_IN("load_images")
        global input_image_list
        global output_image_list
     
        x1=get_web_images()       
        input_image_list=extract_input_images(x1)
      
        #TRACE_OUT("load_images")
        return gallery_images()
    
    def gallery_images():
        #TRACE_IN("gallery_images")
        global input_image_list
        global output_image_list

        x_in=[]    
        for x in input_image_list:
            x_in.append(x["img"])
                
        x_out=[]
        for x in output_image_list:
            x_out.append(x["img"])
 
        #TRACE_OUT("gallery_images")      
        return x_in,x_out,f"## {len(x_out)} selected"

                
    def move_image(x1,x2):
        #TRACE_IN("move_image")
        global selected_index
        
        if not len(x1):
            selected_index=0
            return
        
        if selected_index >= len(x1):
            selected_index=len(x1)-1
                   
        x2.append(x1[selected_index])
        x1.pop(selected_index)
        
        #TRACE_OUT("move_image")
        return
                    
    def clear_selected():
        global output_image_list
        output_image_list.clear()
        return gallery_images()
             
    def swap_image():
        #TRACE_IN("swap_image")
        global selected_label
           
        if (selected_label == "input_gallery"):
            move_image(input_image_list,output_image_list)
            
        if (selected_label == "output_gallery"): 
            move_image(output_image_list,input_image_list)
           
        #TRACE_OUT("swap_image")           
        return gallery_images()
        
    def get_ext(url):
        parsed = urlparse(url)
        root,ext = splitext(parsed.path)
        return ext
       
    def dirname():
        global search_term
        global save_path
          
        sname=sanitize_filename(search_term)
        if not sname:
            sname="random-images"
                   
        dname=f"{save_path}/{sname}"

        if not os.path.exists(dname):
            return dname
        i=1
        while os.path.exists(f"{dname}-{i}"):
            i=i+1   
                  
        return f"{dname}-{i}"
        

    def save_images(): 
        #TRACE_IN("save_images")
        global output_image_list 
        dname=dirname()
        os.makedirs(dname,exist_ok=True)
         
        i=0;
        for x in output_image_list:      
            url=x["murl"]     
            headers = {'User-Agent': user_agent_string()}         
            rsp=requests.get(url,headers=headers)
            
            ext=get_ext(url)   
            #DEBUG(ext)
            if not ext:
                hdr_ext=rsp.headers['Content-Type']
                #DEBUG(hdr_ext)
                z=hdr_ext.split('/')
                if z[0] == 'image':
                    ext = "."+z[1]
                    #DEBUG(ext)
                    #DEBUG(z[1])
                else:
                    ERROR(f"Unknown File Type:{url}")
                    continue
            i=i+1;
            fname=f"{dname}/{i}{ext}"
            
            with open(fname,'wb') as f:           
                f.write(rsp.content)
     
        #TRACE_OUT("save_images")
        return clear_selected()
       
    def on_gallery_select(evt: gr.SelectData):
        #TRACE("on_gallery_select")
        global selected_index
        global selected_label
        
        selected_index=evt.index
        selected_label=evt.target.label
        return
          
    def on_searchbox_input(evt: gr.EventData):
        #TRACE("on_searchbox_input")
        global search_term
        search_term=evt._data
        return   
        
    def on_engine_change(evt: gr.EventData):
        #TRACE("on_engine_change")
        global search_engine
        search_engine=evt._data
        #DEBUG(search_engine)
        return 
        
    with gr.Row():
        input_gallery = gr.Gallery(label="input_gallery",columns=num_columns)
            
    with gr.Row():
    
        with gr.Column():
            search_str_box = gr.Textbox(label="Search Term",value=search_term,interactive=True)
            update_btn = gr.Button(value="Update")  
                     
        with gr.Column():      
            swap_btn = gr.Button(value="Select/Deselect") 
            with gr.Row():
                
                with gr.Row():
                    engine_btn = gr.Radio(["Google","Bing"],container=False,value=search_engine,interactive=True)
                    status_box = gr.Markdown("## None selected")
                    
            save_btn = gr.Button(value="Save") 
                       
    with gr.Row():
        output_gallery = gr.Gallery(label="output_gallery",columns=num_columns)   
    
    output_gallery.select(on_gallery_select)           
    input_gallery.select(on_gallery_select)   
    search_str_box.change(on_searchbox_input)    
    engine_btn.change(on_engine_change)   
    selector.load(load_images,None,[input_gallery,output_gallery])
    update_btn.click(load_images,None,[input_gallery,output_gallery]) 
    swap_btn.click(swap_image,None,[input_gallery,output_gallery,status_box])  
    save_btn.click(save_images,None,[input_gallery,output_gallery,status_box])
        
if __name__ == "__main__":
    selector.launch()
    #selector.launch(share=True)
