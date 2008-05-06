import mimetypes
import os.path
import sys
from datetime import datetime, timedelta
from optparse import make_option

from django.core.management.base import NoArgsCommand
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

class Command(NoArgsCommand):
    option_list = NoArgsCommand.option_list + (
        make_option('--verbose', action='store_true', dest='verbose',
            help = 'Verbose mode for you control freaks'),
        make_option('--no-gzip', action='store_true', dest='no_gzip',
            help = 'Switches OFF gzip compression'),
        make_option('--no-expires', action='store_true', dest='no_expires',
            help = 'No far future Expires header'),
    )
    help = """Upload static media files to a S3 bucket.
    
    Usage:
        $cd static_media
        $find * | grep -v ".svn" | .././manage.py upload_to_s3
    
    Each line written to the STDIN must be a /path/to/file to be uploaded to a S3 bucket.
    """
    def handle_noargs(self, **options):
        # handle command-line options
        verbose = options.get('verbose', False)
        def log(msg, error=False):
            if verbose or error:
                print msg
        
        no_gzip = options.get('no_gzip', False)
        no_expires = options.get('no_expires', False)
        
        if not ( hasattr(settings, "AWS_ACCESS_KEY_ID") and 
                    hasattr(settings, "AWS_SECRET_ACCESS_KEY") and
                    hasattr(settings, "BUCKET_NAME") ):
            log(
                "Error: You need to add AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY & BUCKET_NAME to your SETTINGS file\n",
                error=True
            )
            sys.exit(1)
        else:
            AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
            AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
            BUCKET_NAME = settings.BUCKET_NAME

            conn = S3.AWSAuthConnection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
            for line in sys.stdin:
                filename = os.path.normpath(line[:-1])
                if filename == '.' or not os.path.isfile(filename):
                    continue # Skip this, because it's not a file.
                
                log("Uploading %s" % filename)
                # guess content-type
                content_type = mimetypes.guess_type(filename)[0]
                if not content_type:
                    content_type = 'text/plain'
                upload_options = {
                    'x-amz-acl': 'public-read',
                    'Content-Type': content_type,
                }
                
                filedata = open(filename, 'rb').read()
                
                # gzip compression
                if not no_gzip:
                    filedata = _compress_string(filedata)
                    content_encoding = 'gzip'
                    upload_options['Content-Encoding'] = 'gzip'
                
                # set far future expires
                if not no_expires:
                    expires = (datetime.now() + timedelta(days=FAR_FUTURE_EXPIRY)).strftime(HTTP_DATE)
                    upload_options['Expires'] = expires
                
                conn.put(
                    BUCKET_NAME, filename, S3.S3Object(filedata),
                    upload_options
                )
