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
import shutil


def cleanup(target, days, dryrun = False):
    logging.info("Cleaning old movies, days to keep {}...".format(days))
    cameras = os.listdir(target)
    for camera in cameras:
        logging.info("Cleanup of camera {}".format(camera))
        day_dirs = sorted(os.listdir(os.path.join(target, camera, 'record')), reverse = True)
        for day_dir in day_dirs[days:]:
            logging.info("Removing {}".format(day_dir))
            if dryrun:
                logging.info('DRY-RUN. Skipped.')
            else:
                shutil.rmtree(os.path.join(target, camera, 'record', day_dir), True)
    logging.info("Cleaning done.")

def organize(target, dryrun = False):
    # Foscam writes into the root FTP directory as follows:
    # <camera_id>/record/[S|M]Dalarm_YYYYMMDD_HHMMSS.mkv
    # What we want to do, is move those files into directories:
    # <camera_id>/record/YYYYMMDD/HH/[S|M]Dalarm_YYYYMMDD_HHMMSS.mkv

    cameras = os.listdir(target)
    for camera in cameras:
        logging.info("Processing camera {}".format(camera))
        movies = os.listdir(os.path.join(target, camera, 'record'))
        for movie in movies:
            if not movie[1:].startswith('Dalarm_'):
                continue
            logging.info("Processing movie {}".format(movie))
            yyyymmdd = movie.split('_')[1]
            hh = movie.split('_')[2 ][:2]
            new_dir = os.path.join(target, camera, 'record', yyyymmdd, hh)
            logging.info("Moving file {} to {}".format(movie, new_dir))
            if not os.path.isdir(new_dir):
                if dryrun:
                    logging.info("DRY-RUN. Make directory skipped")
                else:
                    os.makedirs(new_dir)
            if dryrun:
                logging.info("DRY-RUN. Moving file skipped.")
            else:
		try:
                	shutil.move(os.path.join(target, camera, 'record', movie), new_dir)
		except Exception as e:
			traceback.print_exc()





def main():

    parser = argparse.ArgumentParser(description='Foscam FTP store - movie file organizer')
    parser.add_argument('--log', help='Log file', default='organizer.log')
    parser.add_argument('--target', help='Path to target FTP root directory to organize', default='ftp')
    parser.add_argument('--dryrun', help='Just print, do nothing', action='store_true', default=False)
    parser.add_argument('--keep_days', help='Number of days of history to keep in archive', default=10,
                        type = int)


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

    logging.info('Foscam organizer started.')
    organize(args.target, args.dryrun)
    cleanup(args.target, args.keep_days, args.dryrun)
    logging.info('Foscam organizer finished.')



if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt as e:
		traceback.print_exc()
	except Exception as e:
		traceback.print_exc()
