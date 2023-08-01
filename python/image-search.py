import requests
import sys
import os
import random
from urllib.parse import urlparse  
from PIL import Image
from io import BytesIO
from pathvalidate import sanitize_filename
from os.path import splitext
from inspect import getmembers
from pprint import pprint

def var_dump(x):
    pprint(vars(x))

       
subscription_key = sys.argv[1]
save_path = sys.argv[2]
search_term = ""
min_width=1024
min_height=1024
num_images=25
offset=0
input_image_list=[]
output_image_list=[]

selected_label=None
selected_index=None
    
import gradio as gr
with gr.Blocks() as selector:
  
    def get_web_images():
        global subscription_key
        global search_term
        global num_images
        global offset
        global min_width
        global min_height
        
        s1=search_term

        if not s1:
            s1="random stuff"
        search_url = "https://api.bing.microsoft.com/v7.0/images/search"
        headers = {"Ocp-Apim-Subscription-Key" : subscription_key}
        params  = {"q": s1,"count":num_images,"offset":offset, "mkt":"en-AU", "license": "any", "imageType": "photo", "minWidth":min_width,"minHeight":min_height}
        
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        
        ret=response.json()
        offset=ret["nextOffset"]
        
        return ret
        
    def user_agent_string():
        agents=[
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",      
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5.2 Safari/605.1.1",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.188"]
        n=len(agents)-1      
        return agents[random.randint(0,n)]

    def extract_input_images(x1):
        images=[]
 
        for x in x1["value"]:
            thb=x["thumbnail"]
            url=x["thumbnailUrl"]
            headers = {'User-Agent': user_agent_string()}
            rsp=requests.get(url,headers=headers)
            img = Image.open(BytesIO(rsp.content))            
           
            image={  "id":x["imageId"],
                     "thumbnail":{"url":url,
                                  "width":thb["width"],
                                  "height":thb["height"],
                                  "img":img},       
                     "image":{"url":x["contentUrl"],
                              "width":x["width"],
                              "height":x["height"]} }                      
            images.append(image)         
        return images         
       
    def load_images():
        global input_image_list
        global output_image_list
     
        x1=get_web_images()       
        input_image_list=extract_input_images(x1)
      
        return gallery_images()
    
    def gallery_images():
        global input_image_list
        global output_image_list

        x_in=[]
        for x in input_image_list:
            thmb=x["thumbnail"]
            x_in.append(thmb["img"])
                
        x_out=[]
        for x in output_image_list:
            thmb=x["thumbnail"]
            x_out.append(thmb["img"])
               
        return x_in,x_out,f"## {len(x_out)} selected"

                
    def move_image(x1,x2):
        global selected_index
        
        if not len(x1):
            selected_index=0
            return
        
        if selected_index >= len(x1):
            selected_index=len(x1)-1
                   
        x2.append(x1[selected_index])
        x1.pop(selected_index)
        
        return
                    
    def clear_selected():
        global output_image_list
        output_image_list.clear()
        return gallery_images()
             
    def swap_image():
        global selected_label
           
        if (selected_label == "input_gallery"):
            move_image(input_image_list,output_image_list)
            
        if (selected_label == "output_gallery"): 
            move_image(output_image_list,input_image_list)
                  
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
        global output_image_list 
        dname=dirname()
        os.makedirs(dname,exist_ok=True)
         
        i=0;
        for x in output_image_list:      
            url=x["image"]["url"]
            ext=get_ext(url)
            i=i+1;
            fname=f"{dname}/{i}{ext}"                
            headers = {'User-Agent': user_agent_string()}             
            with open(fname,'wb') as f:
                rsp=requests.get(url,headers=headers)
                f.write(rsp.content)

      
        return clear_selected()
       
    def on_select(evt: gr.SelectData):
        global selected_index
        global selected_label
        
        selected_index=evt.index
        selected_label=evt.target.label
          
    def on_input(evt: gr.EventData):
        global search_term
        global offset
        offset=0
        search_term=evt._data
        return   
 
    with gr.Row():
        input_gallery = gr.Gallery(label="input_gallery",columns=3)
            
    with gr.Row():
        with gr.Column():
            search_str_box = gr.Textbox(label="Search Term", value=search_term)
            update_btn = gr.Button(value="Update")  
                     
        with gr.Column():      
            swap_btn = gr.Button(value="Select/Deselect") 
            status_box = gr.Markdown("## None selected")
            save_btn = gr.Button(value="Save") 
                       
    with gr.Row():
        output_gallery = gr.Gallery(label="output_gallery",columns=3)   
        output_gallery.select(on_select)
               
    input_gallery.select(on_select)   
    search_str_box.change(on_input)      
    selector.load(load_images,None,[input_gallery,output_gallery])
    update_btn.click(load_images,None,[input_gallery,output_gallery]) 
    swap_btn.click(swap_image,None,[input_gallery,output_gallery,status_box])  
    save_btn.click(save_images,None,[input_gallery,output_gallery,status_box])
        
if __name__ == "__main__":
    selector.launch()

