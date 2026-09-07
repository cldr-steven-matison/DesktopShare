import json
from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult

class GenericTransformTemplate(FlowFileTransform):
    # Mandatory: Registers the processor with the NiFi backend
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '0.0.1-BASE'
        description = 'Bare-minimum framework to test NiFi UI integration.'
        tags = ['template', 'framework']

    def __init__(self, **kwargs):
        # 'pass' is the safest initialization in many containerized environments
        pass

    def transform(self, context, flowfile):
        contents_str = flowfile.getContentsAsBytes().decode('utf-8')
        attributes = flowfile.getAttributes()

        # Route directly to success without modification
        return FlowFileTransformResult(
            relationship='success',
            attributes=attributes,
            contents=contents_str
        )
