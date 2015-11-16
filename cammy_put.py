#!/usr/bin/python

import sys
import os.path
import os
import time
import fcntl
import traceback
import logging
import logging.handlers
import argparse
from ftplib import FTP
import ftplib
import shutil
from PIL import Image
import subprocess

PIDLOCKFP = None
FTPH = None

def is_running(pidfname):
	global PIDLOCKFP
	PIDLOCKFP = open(pidfname, 'w') 
	try:
		fcntl.lockf(PIDLOCKFP, fcntl.LOCK_EX | fcntl.LOCK_NB)
		PIDLOCKFP.write("{0}\n".format(os.getpid()))
		PIDLOCKFP.flush()
	except IOError:
		return True
	return False



def cleanup(pidfname):
	global PIDLOCKFP
	PIDLOCKFP.close()	
	os.remove(pidfname)




def get_dirsize(directory):
	dir_size = 0
	for (path, dirs, files) in os.walk(directory):
		for file in files:
			filename = os.path.join(path, file)
			dir_size += os.path.getsize(filename)
	return dir_size

def get_dirsize2(directory):
	logging.info("Computing dir size ... {} ".format(directory))
	dir_size = subprocess.check_output(['du','-s', directory]).split()[0].decode('utf-8')
	logging.info("Computing dir size done.")
	return dir_size	

   
def archive_image(imagedir, imagefile, archivedir):
	dirsize = get_dirsize2(archivedir)
	while dirsize > (1024*1024*1024)*5:
		fnames = get_images(archivedir)
		logging.info("Spring cleaning {}/{}".format(archivedir,fnames[0]))
		os.remove(os.path.join(archivedir,fnames[0]))
		dirsize = get_dirsize(archivedir)

	logging.info("Archiving {}, dirsize {}".format(imagefile,dirsize))
	shutil.copy(os.path.join(imagedir,imagefile), archivedir)
	logging.info("Archiving {} completed.".format(imagefile))



def archive_image2(imagedir, imagefile, archivedir, dirsize):
	targetfname = os.path.join(archivedir, imagefile)
	if os.path.isfile(targetfname):
		logging.info("Target file already exists. Skipping. {}".format(targetfname))
		return dirsize

	while dirsize > (1024*1024*1024):
		fnames = get_images(archivedir)
		f = os.path.join(archivedir,fnames[0])
		fsize = os.path.getsize(f)
		logging.info("Spring cleaning {}".format(f))
		os.remove(f)
		dirsize -= fsize

	logging.info("Archiving {}, dirsize {}".format(imagefile,dirsize))
	imgfname = os.path.join(imagedir,imagefile)
	shutil.copy(imgfname, archivedir)
	dirsize += os.path.getsize(imgfname)
	return dirsize


def archive_images(imagedir, archivedir):
	dirsize = get_dirsize(archivedir)
	for fname in get_images(imagedir):
		dirsize = archive_image2(imagedir, fname, archivedir, dirsize)

def resize_image(imagedir, imagefname):
	if imagefname.endswith('_sml.jpg'):
		return imagefname
	infile = os.path.join(imagedir, imagefname)
	im = Image.open(infile)
	im.thumbnail( (2000,720) )
	a,b = os.path.splitext(imagefname)
	outfname = a + "_sml" + b 
	im.save(os.path.join(imagedir, outfname), "JPEG", quality = 70)
	logging.info('Resizing {} to {}'.format(infile, outfname))
	return outfname

def get_images(image_dir):
	fnames = sorted(os.listdir(image_dir))
	return fnames

def ftp_callback(block):
	logging.info('Sent block...')

def get_ftphandle(username, password):
	global FTPH
	if not FTPH:
		logging.info('Connecting to FTP server.')
		FTPH = FTP(timeout=60)
		FTPH.set_debuglevel(2)
		FTPH.connect('ftp.cammy.com',10021)
		FTPH.login(username, password) #'1NK0RU','bebifefo')
	return FTPH

def close_ftphandle():
	global FTPH
	try:
		if FTPH:
			FTPH.quit()
	except ftplib.all_errors as e:
		logging.exception('Exception during closing the FTP handle')
	FTPH = None

def ftp_put(ftph, imagedir, imagefile):
	sent = False
	try:
		imagefname = os.path.join(imagedir, imagefile)
		logging.info("FTP STOR {}".format(imagefname))
		#resp = ftph.storbinary("STOR " + imagefile, open(imagefname,'rb'), blocksize = (8192*3), callback = ftp_callback)
		resp = ftph.storbinary("STOR " + imagefile, open(imagefname,'rb'), blocksize = 4096, callback = ftp_callback)
		ftph.voidcmd('NOOP')
		logging.info("FTP STOR response code {}".format(resp))
		sent = True
	except ftplib.all_errors as e:
		logging.exception('Exception during putting image')
	except Exception as e:
		logging.exception('Unexpected exception during putting image')
	return sent

def remove_image(imagedir, fname):
	f = os.path.join(imagedir, fname)
	if os.path.isfile(f):
		logging.info("Removing {}".format(f))
		os.remove(f)
		
def get_fileage(imagedir, fname):
	return int( time.time() - os.path.getctime(os.path.join(imagedir,fname)) )

def ftp_putall(imagedir, username, password, delete, archivedir, resize):
	fnames = get_images(imagedir)

	if archivedir:
		archive_images(imagedir, archivedir)
		

	i = 0
	retrycount = 0

	for i in range(len(fnames)):
		fname = fnames[i]

		# TODO: this needs testing
		if get_fileage(imagedir, fname) > (60*60) and delete:
			logging.warning("Frame drop! Dropping {}".format(fname))
			remove_image(imagedir, fname)
			continue

		if fname.endswith('_sml.jpg'):
			continue

		orig_fname = fname


		if resize:
			fname = resize_image(imagedir, fname)

		ftph = get_ftphandle(username, password)
		ok = ftp_put(ftph, imagedir, fname)

		if ok and delete:
			remove_image(imagedir, fname)
			remove_image(imagedir, orig_fname)
			

		if not ok:
			logging.info('Problem during storing {}, retrying'.format(fname))
			close_ftphandle()
			retrycount += 1
			if retrycount > 10:
				logging.error('Retry count exceeded... giving up!')
				return
			i -= 1 # Step backwards!
		else:
			retrycount = 0

	close_ftphandle()
	
	

def main():

	parser = argparse.ArgumentParser(description='Cammy FTP Uploader.')
	parser.add_argument('-u', dest='username', required=True, help='Cammy FTP username')
	parser.add_argument('-p', dest='password', required=True, help='Cammy FTP password')
	parser.add_argument('--log', help='Log file path', default='cammyput.log')
	parser.add_argument('--imagedir', help='Path to images', default='images')
	parser.add_argument('--pidfile', help='Path to pid runfile', default='/var/run/motion/cammyput.pid')
	parser.add_argument('--delete', help='Delete images are uploading', action='store_true', default=False)
	parser.add_argument('--resize', help='Resize images before sending to cammy', action='store_true', default=False)
	parser.add_argument('--archivedir', help='Archive directory', default=None)

	args = parser.parse_args()

	logFormatter = logging.Formatter("%(asctime)s [%(levelname)-5.5s]  %(message)s")
	rootLogger = logging.getLogger()
	fileHandler = logging.handlers.RotatingFileHandler(args.log, maxBytes=(1048576*5), backupCount=7)
	fileHandler.setFormatter(logFormatter)
	rootLogger.addHandler(fileHandler)

	consoleHandler = logging.StreamHandler(sys.stdout)
	consoleHandler.setFormatter(logFormatter)
	rootLogger.addHandler(consoleHandler)

	rootLogger.setLevel(logging.DEBUG)

	logging.info('CammyPut started.')
	if is_running(args.pidfile):
		logging.warning("CammyPut is already running. Skipping.")
		return



	more = True
	while more:
		ftp_putall(args.imagedir, args.username, args.password, args.delete, args.archivedir, args.resize)
		if len(get_images(args.imagedir))>0 and args.delete:
			more = True
			logging.info('More images to upload, sending again.')
		else:
			more = False
	cleanup(args.pidfile)
	logging.info("Finished")


if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt as e:
		traceback.print_exc()
	except Exception as e:
		traceback.print_exc()
