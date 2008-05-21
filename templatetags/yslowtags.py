from django.template import Node, NodeList, Template, Context, Variable, Library
from django.template import TemplateSyntaxError, VariableDoesNotExist
from django.conf import settings
from yslow import utils

register = Library()

def ifprod(parser, token):
    """Replace multiple <script> or <link rel="stylesheet"> tags with one tag pointing to the concatenated file.
    
    Concatenated file has to be generated prior to this, by running the management command "build".
    
    If optimization is OFF, replaces enclosed <script> tags with one <script> tag.
    If optimization is ON, does nothing.
    
    It makes sure to include a script or css stylesheet only once per entire template.
    """
    args = token.split_contents()
    if len(args)!=2:
        raise TemplateSyntaxError("%r requires exactly 1 argument" % args[0])

    nodelist = parser.parse(('endifprod', )) # include everything until endifprod (excluding endifprod itself)
    parser.delete_first_token() # deleting endifprod
    
    if not hasattr(parser, '_ifprodNodes'):
        parser._ifprodNodes = {}
    
    if not parser._ifprodNodes.has_key(args[1]):
        parser._ifprodNodes[args[1]] = IfProdNode(nodelist, args[1].replace('"',''))
    return parser._ifprodNodes[args[1]]
ifprod = register.tag(ifprod)

class IfProdNode(Node):
    def __init__(self, nodelist, new_file):
        self.nodelist = nodelist
        self.new_file = new_file
        self.rendered = False
    
    def render(self, context):
        if not utils.should_optimize():
            return self.nodelist.render(context)
        elif not self.rendered:
            resolved_new_file = Template(self.new_file).render(context)
            if self.new_file.endswith(".js"):
                self.rendered = True
                return '<script src="%s" type="text/javascript"></script>' % resolved_new_file
            elif self.new_file.endswith(".css"):
                self.rendered = True
                return '<link href="%s" rel="stylesheet" type="text/css"/>' % resolved_new_file
            else:
                return ''
        else:
            return ''
