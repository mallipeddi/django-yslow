import os, shutil, subprocess, sys
import re
from optparse import make_option

from django.core.management.base import NoArgsCommand
from django.conf import settings

class Command(NoArgsCommand):
    option_list = NoArgsCommand.option_list + (
        make_option('--keep-hidden', action='store_true', dest='keep_hidden',
            help = 'Keep hidden files/folders in the build. By default, .git/.svn/etc are not ignored'),
        make_option('--verbose', action='store_true', dest='verbose',
            help = 'Verbose mode for you control freaks'),
        make_option('--compress-inline-script', action="store_true", dest="compress_inline_script",
            help = '(experimental) Compress inline <script> tags. Needs BeautifulSoup.'),
        make_option('--compress-inline-style', action="store_true", dest="compress_inline_style",
            help = '(experimental) Compress inline <style> tags. Needs BeautifulSoup.'),
        make_option('--disable-versioning', action="store_true", dest="disable_versioning",
            help = 'Disable versioning (versioning is useful if you want to set a Far Future Expires on your static media)'),
    )
    help = """
    Builds a production-ready compressed package of the Django project.
    Needs YUI Compressor.
    """
    
    def handle_noargs(self, **options):
        # command-line options
        verbose = options.get('verbose', False)
        def log(msg, error=False):
            if verbose or error:
                print msg
        
        keep_hidden = options.get('keep_hidden', False)
        compress_inline_script = options.get('compress_inline_script', False)
        compress_inline_style = options.get('compress_inline_style', False)
        if compress_inline_style or compress_inline_style:
            try:
                from BeautifulSoup import BeautifulSoup
            except ImportError, e:
                log("ERROR - Install BeautifulSoup ($easy_install BeautifulSoup).", error=True)
                sys.exit(1)
        disable_versioning = options.get('disable_versioning', False)

        # settings file options
        if hasattr(settings, 'CONCATS'):
            concats = settings.CONCATS
        else:
            concats = ()
        if not disable_versioning:
            if hasattr(settings, 'VERSION'):
                version = settings.VERSION
            else:
                log("Warning - you've asked for versioning of static media but not explicitly set a VERSION string in SETTINGS file")
                log("Using the default VERSION=\"v1\".")
                version = "v1"
        
        settings_folder = os.getcwd() # the folder containing settings.py for the target Django project
        if hasattr(settings, 'BUILD_FOLDER'):
            build_folder = settings.BUILD_FOLDER
        else:
            build_folder = os.path.join(settings_folder, "../" + os.path.basename(settings_folder) + "-build")
            log("No BUILD_FOLDER found in SETTINGS file. Using %s instead" % os.path.abspath(build_folder))
        if hasattr(settings, 'YUICOMPRESSOR_JAR'):
            yuix = settings.YUICOMPRESSOR_JAR
        elif os.environ.has_key('YUICOMPRESSOR_JAR'): # look for YUICOMPRESSOR_JAR environ variable
            yuix = os.environ['YUICOMPRESSOR_JAR']
        else:
            log("Error - You need to specify YUICOMPRESSOR_JAR in SETTINGS or add an environment variable.", error=True)
            sys.exit(1)

        def get_file_extension(filename):
            return filename.split('.')[-1].lower()
        
        def get_versioned_filename(filename):
            if disable_versioning:
                return filename
            tmp = filename.split('.')
            if tmp:
                new = tmp[:-1]
                new.append(version)
                new.append(tmp[-1])
                return '.'.join(new)
            else:
                return filename
        
        def yuicompress(input, output):
            """Compress the contents of input file and write to the output file.
            
            Args:
                * input, output - full path to files
            """
            log("Compressing %s..." % input)
            ret = subprocess.call("java -jar %s %s -o %s" % (yuix, input, output),
                                shell = True,
                                stdout = open('/dev/null','w'),
                                stderr = subprocess.STDOUT
                    )
            if ret != 0:
                log("yuicompressor: compressing %s failed." % input, error=True)
        
        def yuicompress_inline(input, input_type="js"):
            """Return compressed form of the input JS/CSS string
            
            Just like yuicompress() but pipes the input to the stdin of the jar cmd
            and gathers the output from the stdout.
            
            Args:
                * input - a string
                * input_type - "js" or "css"
            Returns: string
            """
            p = subprocess.Popen("java -jar %s --type %s" % (yuix, input_type),
                                shell = True,
                                stdin = subprocess.PIPE,
                                stdout = subprocess.PIPE,
                                close_fds = True
                            )
            output, errors = p.communicate(input.encode('utf-8'))
        
        def handle_pyc(srcfolder, file, target):
            pass # do nothing
        
        def handle_default(srcfolder, file, target):
            log("Copying %s to %s" % (os.path.abspath(os.path.join(srcfolder, file)), target))
            shutil.copy(os.path.join(srcfolder, file), target)
        
        def handle_js(srcfolder, file, target):
            jsin = os.path.join(srcfolder, file)
            jsout = os.path.join(target, get_versioned_filename(file))
            if not is_in_concats(jsin): # if js file is not meant to be concatenated
                yuicompress(jsin, jsout)
        
        def handle_css(srcfolder, file, target):
            cssin = os.path.join(srcfolder, file)
            cssout = os.path.join(target, get_versioned_filename(file))
            if not is_in_concats(cssin):
                yuicompress(cssin, cssout)
                handle_css_image_versioning(cssout)
        
        def handle_css_image_versioning(src):
            if disable_versioning:
                return # do nothing
            # handle versioning of images automatically in CSS files
            # since no template variables are available to the user
            # this looks for url(*.png|gif|jpg) patterns in the CSS file
            css_fin = open(src,"r")
            s = css_fin.read()
            css_fin.close()
            css_fout = open(src,"w")
            exp = re.compile(r'url\((.*?)\.(png|gif|jpg)\)')
            css_fout.write(
                exp.sub(
                    lambda m: "url(%s.%s.%s)" % (m.group(1), version, m.group(2)),
                    s
                )
            )
            css_fout.close()
        
        def handle_images(srcfolder, file, target):
            imgin = os.path.join(srcfolder, file)
            imgout = os.path.join(target, get_versioned_filename(file))
            shutil.copyfile(imgin, imgout)
        
        def handle_html(srcfolder, file, target):
            "Minify inline <script> and <style> tags."
            
            if not compress_inline_script and not compress_inline_style:
                handle_default(srcfolder, file, target)
                return
            from BeautifulSoup import BeautifulSoup
            htmlin = os.path.join(srcfolder, file)
            htmlout = os.path.join(target, file)
            fin = open(htmlin, "r")
            soup = BeautifulSoup(fin)
            if compress_inline_script:
                for script in soup('script'):
                    if script.contents:
                        script.replaceWith(yuicompress_inline(script.contents[0]))
            elif compress_inline_style:
                for style in soup('style'):
                    if style.contents:
                        style.replaceWith(yuicompress_inline(style.contents[0], "css"))
            fout = open(htmlout, "w")
            fout.write(str(soup))
            fin.close()
            fout.close()
            
        def copy_recursive(srcfolder, targetparent):
            target = os.path.join(targetparent, os.path.basename(srcfolder))
            os.mkdir(target)
            for item in os.listdir(srcfolder):
                if item and item[0] == '.' and (not keep_hidden):
                    continue
                srcitem = os.path.join(srcfolder, item)
                if os.path.isfile(srcitem):
                    try:
                        handle_file = {
                            'pyc': handle_pyc,
                            'js': handle_js,
                            'css': handle_css,
                            'html': handle_html,
                            'gif': handle_images,
                            'jpg': handle_images,
                            'png': handle_images,
                        }[get_file_extension(item)]
                        handle_file(srcfolder, item, target)
                    except KeyError, e:
                        handle_default(srcfolder, item, target)
                elif os.path.isdir(srcitem):
                    copy_recursive(os.path.join(srcfolder, item), target)

        def handle_concats():
            """Concatenates multiple files into single files
            
            Concatenates based on concatenation rules specified in project settings file.
            """
            for rule in concats:
                src = os.path.join(settings_folder, rule[0])
                dst = os.path.join(os.path.join(build_folder, os.path.basename(settings_folder)), rule[1])
                dst = get_versioned_filename(dst)
                append_file(src, dst)
            
            # compress the final output files generated above
            s = set(
                (
                    get_versioned_filename(
                        os.path.join(os.path.join(build_folder, os.path.basename(settings_folder)), rule[1])
                    ) for rule in concats
                )
            )
            for dst in s:
                yuicompress(dst, dst)
                handle_css_image_versioning(dst)

        def is_in_concats(file):
            for rule in concats:
                if os.path.join(settings_folder, rule[0]) == file:
                    return True
        
        def append_file(src, dst):
            fin = open(src, "r")
            fout = open(dst, "a")
            for line in fin:
                fout.write(line)
            fin.close()
            fout.close()
        
        if os.path.exists(build_folder):
            shutil.rmtree(build_folder)
        os.mkdir(build_folder)
        copy_recursive(settings_folder, build_folder)
        # handle JS & CSS concatenations
        handle_concats()
