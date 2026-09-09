from . import core as _core
from .core import convert
from .pdf_layout import convert_pdf_to_docx

# convert() resolves pdf_to_docx from converters.core at runtime, so patch that
# hook to use the line-positioned editable text-box implementation.
_core.pdf_to_docx = convert_pdf_to_docx
