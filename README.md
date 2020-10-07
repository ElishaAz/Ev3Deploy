# Ev3Deploy
Transfer code from your computer to the ev3 and run it remotely.

## Requirments
This project supports python 3.4 and up.
To use this project you need to install the scp python package:
```
pip install scp
```
Download `ev3deploy.py` and place it at the root of your project.
## Use
Run
```
python3 ev3deploy.py
```
To copy your project to the ev3.
If you want to run a file on the ev3, run
```
python3 ev3deploy.py --execute_file <file_name>
```
You will see the output of the program in your console.
