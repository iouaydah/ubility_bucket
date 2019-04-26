##
# Code Created by Ismail Ouaydah for ubility and daa solutions - April 2019
###########################################################################
from google.cloud import storage, pubsub_v1

import json
import os
import cv2
import datetime
import time
import numpy as np
import imutils
from skimage import img_as_float
from skimage.measure import compare_ssim as ssim

import logging
from logging.config import fileConfig

fileConfig('logging_config.ini')
logger = logging.getLogger()

referrentdir='./referrent/'
dupliquedir= './duplique/'

localresponse='response.json'
localjson='request.json'

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "reds-ubility-int-000-13ce262dbe7c.json"
bucketname='reds-ubility-process-int-000'
storage_client = storage.Client()
bucket = storage_client.get_bucket(bucketname)

# The `subscription_path` method creates a fully qualified identifier: `projects/{project_id}/subscriptions/{subscription_name}`
project_id = "reds-ubility-int-000"
subscription_name = "requests-main-subscription"
subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(project_id, subscription_name)

topic_name="responses"
publisher = pubsub_v1.PublisherClient()
topic = publisher.topic_path(project_id, topic_name)

def mainflow(message):
    # get the json file from the bucket (with folder name provided in message)then call the jsonprocess
    
    # Check Google queue message attributes
    logtext="message "+ str(message.message_id)+ " published at "+ str(message.publish_time)+ " received by ubility..."
    logger.info(logtext)
    if message.attributes:
        for key in message.attributes:
            value = message.attributes.get(key)
            logger.debug("message attributes: "+key+":"+value)
            
    folder='.'
    # get the folder from id or job_id attribute
    if(message.attributes.get('id')):
        folder=str(message.attributes.get('id'))
    
    if(message.attributes.get('job_id')):
        folder=str(message.attributes.get('job_id'))
    
    remotepath=folder+'/request.json'
    localjsonpath='./jsonsource/'+folder+ localjson #eachjob will have a different filename
    logger.info(folder)
    
    message.ack()
    
    if(folder !='.'):
        try:
            logger.info('Downloading json source for: '+folder)
            blob = bucket.blob(remotepath)
            blob.download_to_filename(localjsonpath)   
        except:
            logger.warning('Error downloading source json '+remotepath)    
        
        logger.info('call jsonprocess for: '+folder)
        jsonprocess(folder,localjsonpath) #might exit with an exception
     
    else:
        logger.warning('job_id or id not provided in the message. will disregard message:'+ str(message.message_id))
       
    #push a message saying job is done. NB: it should be a byte string
    logger.info ("publishing response to queue for job: "+folder )
    publisher.publish(topic, b'Job done', job_id=folder)


#################################################################################    
def jsonprocess(folder,localjsonpath):
    #parse json to create lists and then call comparelists, upload the response.json to the bucket
    json_file=open(localjsonpath)    
    data=json.load(json_file)

    # used to build support lists    
    referrentlist = []
    dupliquelist = []
    
    # create directories to download each job images in different folder
    logger.info("donwloading images for:"+folder)
    rootfolder=str(data['id'])+'/'
    refdir=referrentdir+rootfolder
    dupdir=dupliquedir+rootfolder
    try:
        os.mkdir(refdir)
        os.mkdir(dupdir)
    except:
        logger.warning ("local directories exist")
                
    try:
        for support in data['family']:
        
            logger.debug("support"+str(support['id']))
            forprocess= support['is_process_required']
            pieces=support['pieces']
            for piece in pieces:
                remotepath= piece['file_path']
                fileid=piece['id']
                x=remotepath.split('/')
                filename=x[len(x)-1]
                if (forprocess): # put in duplique dir else in referrent dir
                    localimagepath=dupdir+filename
                    dupliquelist.append((fileid,localimagepath))  #build support list to be compared
                else:
                    localimagepath=refdir+filename
                    referrentlist.append((fileid,localimagepath)) #build support list to be compared against
                               
                logger.debug("Downloading: "+rootfolder+remotepath)
                # download image from bucket to the corresponding local dir
                blob = bucket.blob(rootfolder+remotepath)
                blob.download_to_filename(localimagepath)
    
        #finished parsing and downloading all images referenced in json source
        #calling comparison function which will create the json response
        matchedfileslist, newpagesfilelist= comparelists(bucketname, folder, dupliquelist, referrentlist) # results saved in the file output
    
    except KeyError:
                logger.warning("error while parsing json source, "+localjsonpath)
                
    except FileNotFoundError as fnf_error:
                print (fnf_error)
    
    #except:
    #            print ("Unknow Error")
                
    finally:
        #empty temp folers
        #print("cleaning up folder ....",folder)
        logger.info("Cleaning up folder:"+folder)
        #for f in os.listdir(refdir):
        #    os.remove(os.path.join(refdir, f))
        #os.rmdir(refdir)
        
        #for f in os.listdir(dupdir):
        #    os.remove(os.path.join(dupdir, f))
        #os.rmdir(dupdir)    
    
    json_file.close()    
    #upload results  the bucket
    responsefilename='./templates/'+folder+localresponse
    if (os.path.isfile(responsefilename)):
        logger.info("uploading response json to the bucket folder:"+folder)
        blob2 = bucket.blob(folder+'/response.json')
        blob2.upload_from_filename(filename=responsefilename)
    
#################################################################################
def comparelists(bucketname, folder, dupliquefilelist, referrentfilelist):    
    #json response file
    responsefilename='./templates/'+folder+localresponse
    outputfile=open(responsefilename,"w+")
    now=datetime.datetime.now()
    lineoftext= "\n.............New Operation Started for: "+folder+".at."+str(now) + "..\n"
    #print(lineoftext)
    logger.info(lineoftext)

    # json response opening and all family process
    jsontext='{\n "version":"1.0" \n"bucket":"'+bucketname+'",\n "job_id":'+folder +' ,\n "pieces":['
    outputfile.write(jsontext)
    
    matchedfileslist={}
    newpagesfilelist=[]
    imagescount=0
    file1counter=0
    for file1 in dupliquefilelist:
        iterationstart=time.time()
        imagescount +=1
                
        lineoftext="\n" +folder+":"+ str(imagescount)+".comparing: "+file1[1]+" referrent list size:"+str(len(referrentfilelist))
        logger.info(lineoftext)
        
        #opening one file1
        if(file1counter==0):
            jsontext='\n{\n"id":'+str(file1[0])+',\n"ubs":[],\n"piece_ref":{\n'
        else:
            jsontext=',\n{\n"id":'+str(file1[0])+',\n"ubs":[],\n"piece_ref":{\n'
            
        outputfile.write(jsontext)

        colorimage1=cv2.imread(file1[1])
        image1 = cv2.imread(file1[1],0)
        (h1, w1) = image1.shape[:2]
        img1 = img_as_float(image1)
        imrange= img1.max() - img1.min()               
        
        similarfound=False
        identicalfound=False
        
        highestssim=0
        ssim_bestmatch_file=''
        
        for file2 in referrentfilelist:
            colorimage2=cv2.imread(file2[1])
            colorimage2= cv2.resize(colorimage2,(w1,h1))
            image2 = cv2.imread(file2[1],0)
            image2= cv2.resize(image2,(w1,h1))
            img2 = img_as_float(image2)
                    
            ssim1 = ssim(img1, img2, data_range=imrange)
            
            if (ssim1 > 0.9998):
                lineoftext=folder+":"+file1[1]+" is matched identical to: " + file2[1] + " SSIM:"+str(round(ssim1,4))
                logger.info(lineoftext)
                
                jsontext=' "id":'+str(file2[0])+',\n"is_identical":true'  
                outputfile.write(jsontext)
                identicalfound=True
                
            elif (ssim1 > 0.89): # it would be 0.89 < ssim1 < 0.9998  This is a similar page that might be New or identical
                lineoftext="    very similar to: "+ file2[1]+ " SSIM:"+str(round(ssim1,4))
                logger.info(lineoftext)
                
                x=file1[1].split('/')
                filename=x[len(x)-1]
                x=filename.split('.')
                filename=x[1]
                x=file2[1].split('/')
                filename=filename+x[len(x)-1]
                filename='./similar_pics/'+filename
                
                jsontext=' "id":'+str(file2[0])+',\n"is_identical":false,\n "matching_rate":'+ str(ssim1)+ ',\n "file_path":"'+ filename +'",' 
                outputfile.write(jsontext)
                        
                # since a simlar page is found let's draw contours around the differences and save it in the folder similar
                (ssim1, diff) = ssim(img1, img2, data_range=img1.max() - img1.min(), full=True)
                diff = (diff * 255).astype("uint8")
                thresh = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
                cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cnts = imutils.grab_contours(cnts)
                
                # slecting the top 5 contours with max area
                cnts=sorted(cnts,key=lambda x:cv2.contourArea(x), reverse=True)
                if(len(cnts)>10):
                    cnts=cnts[:10]
                
                jsontext='\n"areas_diff": [\n'
                outputfile.write(jsontext)
                        
                countforcomma=0
                for c in cnts:
                    #draw the pink rectangles
                    (x, y, w, h) = cv2.boundingRect(c)
                    cv2.rectangle(colorimage1, (x, y), (x + w, y + h), (255, 0, 255), 3)
                        
                    if (countforcomma==0):
                        jsontext='\n     {"x":'+ str(x)+ ',"y":'+ str(y)+ ',"width":'+ str(w)+ ',"height":'+ str(h)+'}'
                    else:
                        jsontext=',\n     {"x":'+ str(x)+ ',"y":'+ str(y)+ ',"width":'+ str(w)+ ',"height":'+ str(h)+'}'
                    outputfile.write(jsontext)
                    countforcomma +=1
                                   
                #closing aeras_diff 
                jsontext='\n]'
                outputfile.write(jsontext)
                
                #save it in the folder ./similar_pics
                vis = np.concatenate((colorimage1, colorimage2), axis=1)
                cv2.imwrite(filename,vis)
                        
                similarfound=True
            
            # still in file2 loop
            if (ssim1> highestssim):
                highestssim= ssim1
                ssim_bestmatch_file=file2
        
            if(identicalfound):
                break #once an identical match is found no need to continue the loop on file2 (conitnue with next file1)
            
        # done comparing one file1 in dupliquelist with all files2 in the referrentlist, will reach here if break from inner loop          
        # one iteration of file1 - closing all pieces_ref and one file1   #closing piece_ref+ one file1
        jsontext='\n}\n}' #jsontext='\n]\n}'
        outputfile.write(jsontext)
        file1counter +=1
        outputfile.flush()
        
        if (not (similarfound or identicalfound)): 
            # not matched we are assuming this is a new page ssim<0.89
            referrentfilelist.append(file1) # I will compare the rest of file1 to this file
            newpagesfilelist.append(file1) #may contain pages that are identical to each other!!!
            lineoftext="  New page..."
            logger.info(lineoftext)
            matchedfileslist[file1]=ssim_bestmatch_file # create a dictionary of best match

        iterationend=time.time() # one iteration in forloop of file1
        onefiletime= round(iterationend-iterationstart,2)
        logger.debug ("time taken:"+str(onefiletime))
    
    #finished all files in dupliquefilelist file1 directory           
    lineoftext="\nPieces comparison completed for folder:"+folder
    #print(lineoftext)
    logger.info(lineoftext)
    
    #closing json response all pieces + json
    jsontext='\n]\n}'
    outputfile.write(jsontext)
    
    outputfile.close()

    return (matchedfileslist, newpagesfilelist)

#########################################################################################
# Limit the subscriber to only have ten outstanding messages at a time.
#flow_control = pubsub_v1.types.FlowControl(max_messages=7)
#subscriber.subscribe(subscription_path, callback=mainflow, flow_control=flow_control)
subscriber.subscribe(subscription_path, callback=mainflow)
# The subscriber is non-blocking. We must keep the main thread from
# exiting to allow it to process messages asynchronously in the background.
print('Listening for messages on {}'.format(subscription_path))
logger.info('Program restarted, Listening for messages')
while True:
    time.sleep(60)