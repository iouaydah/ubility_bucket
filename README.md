## Ubility_bucket_topic V1.0 Release file
## Installation
For the program to run you need to install Python and the following libraries

- OpenCV library: pip install opencv-python
- imutils library: pip install imutils
- sickit learn library: pip install scikit-image
- google.cloud: pip install --upgrade google-cloud-storage
		pip install --upgrade google-cloud-pubsub

configure google environment  
export GOOGLE_APPLICATION_CREDENTIALS="/home/iouaydah/reds-ubility-int-000-13ce262dbe7c.json"

## Usage
Ubility_bucket_topic listen to messages in the request queue, downloads request.json and images from the google bucket.
request message is expected to have an attribute called job_id with value equal to the directory name to be processed.
It compares them and uploads back response.json to the bucket, publish a message to the response queue indicating the job is done. Response message is '<job_id> is done' where <job_id> is the job being processed.

to start the program run >> python ubility_bucket_topic.py

## Expected Json Source format
{
    "id": 27, 
    "bucket": "reds-ubility-process-int-000",
    "family": [
        {
            "id": 203066, # this is support id
            "is_process_required": true,
            "pieces": [
                {
                    "id": 4002808, # this is the piece id
                    "number": 1,
                    "file_path": "file1path.jpg",
                    "ubs": []
                },
                {
                    "id": 4002809,
                    "number": 2,
                    "file_path": "file2path.jpg",
                    "ubs": []
                }
  		]
        },
        {
            "id": 203063,
            "is_process_required": false,
            "pieces": [
                {
                    "id": 4002791,
                    "number": 1,
                    "file_path": "file3path.jpg",
                    "ubs": []
                },
                {
                    "id": 4002792,
                    "number": 2,
                    "file_path": "file4path.jpg",
                    "ubs": []
                }
            ]
        },
        {
            "id": 203064,
            "is_process_required": true,
            "pieces": [
                {
                    "id": 4002796,
                    "number": 1,
                    "file_path": "file5path.jpg",
                    "ubs": []
                }
            ]
        }
    ]
}

## Monitoring
The program log file is ubility.log. Logger configuration is done through file logging_config.ini

processed files are downloaded under ./referrent and ./duplique directories

## Expected Json Response format
{
   "version":"1.0"
   "bucket":"reds-ubility-process-int-000",
   "job_id":39 ,
   "pieces":[
       {
		"id":4002897,
		"ubs":[],
		"piece_ref":{
			 "id":4002825,
			"is_identical":true
			}
	 },
	{
		"id":4002915,
		"ubs":[],
		"piece_ref":{
			 "id":4002843,
			"is_identical":false,
			"matching_rate":0.91287898,
			"file_path":"./similar_pics/jpg20190409082113_5cac55f91a851.jpg",
			"areas_diff": [
		     {"x":38,"y":1658,"width":1583,"height":105},
		     {"x":734,"y":1509,"width":99,"height":25},
		     {"x":836,"y":1509,"width":45,"height":24},
		     {"x":883,"y":1509,"width":41,"height":25},
		     {"x":1038,"y":1509,"width":31,"height":24},
		     {"x":579,"y":1509,"width":30,"height":25},
		     {"x":1070,"y":1514,"width":10,"height":19}
			]
		}
	}
    ]
}