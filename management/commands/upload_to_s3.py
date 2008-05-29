import mimetypes
import os.path
import sys
from datetime import datetime, timedelta
from optparse import make_option

from django.core.management.base import BaseCommand
from django.conf import settings

import S3

FAR_FUTURE_EXPIRY = 365 * 2 # set expires header to this many days from now
HTTP_DATE = "%a, %d %b %Y %H:%I:%S GMT" # adding a %Z did not work!

def _compress_string(s):
    import cStringIO, gzip
    zbuf = cStringIO.StringIO()
    zfile = gzip.GzipFile(mode='wb', compresslevel=6, fileobj=zbuf)
    zfile.write(s)
    zfile.close()
    return zbuf.getvalue()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--verbose', action='store_true', dest='verbose',
            help = 'Verbose mode for you control freaks'),
        make_option('--no-gzip', action='store_true', dest='no_gzip',
            help = 'Switches OFF gzip compression'),
        make_option('--no-expires', action='store_true', dest='no_expires',
            help = 'No far future Expires header'),
    )
    help = """Upload static media files to a S3 bucket.
    
    Usage:
        There are 2 different ways to use this command.
    
        1) Each line written to the STDIN must be a /path/to/file to be uploaded to a S3 bucket.
            $cd static_media
            $find * | grep -v ".svn" | .././manage.py upload_to_s3
            
        2) Alternatively supply the /path/to/src_file & /path/to/dest_file (S3 path)
            $./manage.py upload_to_s3 --verbose static_media/css/widget_iphone.css css/widget_iphone.css
    """
    args = "[SRC DEST]"
    
    def _log(self, msg, error=False):
        if self._verbose or error:
            print msg
    
    def handle(self, *args, **options):
        # handle command-line options
        self._verbose = options.get('verbose', False)
        
        no_gzip = options.get('no_gzip', False)
        no_expires = options.get('no_expires', False)
        
        if not ( hasattr(settings, "AWS_ACCESS_KEY_ID") and 
                    hasattr(settings, "AWS_SECRET_ACCESS_KEY") and
                    hasattr(settings, "BUCKET_NAME") ):
            self._log(
                "Error: You need to add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY & BUCKET_NAME to your SETTINGS file\n",
                error=True
            )
            sys.exit(1)
        else:
            AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
            AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
            BUCKET_NAME = settings.BUCKET_NAME

            conn = S3.AWSAuthConnection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
            
            def _upload(src, dest):
                self._log("Uploading %s to s3:///%s/%s" % (src, BUCKET_NAME, dest))
                
                # guess content-type
                content_type = mimetypes.guess_type(src)[0]
                if not content_type:
                    content_type = 'text/plain'
                upload_options = {
                    'x-amz-acl': 'public-read',
                    'Content-Type': content_type,
                }
                
                filedata = open(src, 'rb').read()
                
                # gzip compression
                if not no_gzip:
                    filedata = _compress_string(filedata)
                    content_encoding = 'gzip'
                    upload_options['Content-Encoding'] = 'gzip'
                
                # set far future expires
                if not no_expires:
                    expires = (datetime.now() + timedelta(days=FAR_FUTURE_EXPIRY)).strftime(HTTP_DATE)
                    upload_options['Expires'] = expires
                
                resp = conn.put(
                        BUCKET_NAME, dest, S3.S3Object(filedata),
                        upload_options
                    )
                self._log(resp.message)

            if len(args) == 0:
                # no args supplied; let us look for input in STDIN
                for line in sys.stdin:
                    filename = os.path.normpath(line[:-1])
                    if filename == '.' or not os.path.isfile(filename):
                        continue # Skip this, because it's not a file.
                    _upload(src=filename, dest=filename)
            elif len(args) == 2:
                # copy src file to dest
                _upload(src=args[0], dest=args[1])
            else:
                self._log("ERROR - Takes in exactly 2 optional args. %d were supplied." % len(args), error=True)
                sys.exit(1)
