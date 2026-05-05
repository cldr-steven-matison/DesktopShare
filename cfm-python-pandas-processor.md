**EXECUTION PLAN: PandasJSONTransformer – NiFi 2.0 Native Python Processor with Pandas**

**Starting Point**  

In this Python Pandas lesson we are picking up where we left off with [Custom NiFi Processors with Cloudera Streaming Operators](https://cldr-steven-matison.github.io/blog/Custom-Processors-With-Cloudera-Streaming-Operators/) and applying the lessons learned and framework from [How to AI with NiFi and Python](How%20to%20AI%20with%20NiFi%20and%20Python.md).

Our existing working environment has:  
- `TransactionGenerator.py` is already placed in the mounted Python extensions directory.  
- The Cloudera Streaming Operators NiFi CR is applied with the live hostPath volume mount active (minikube mount or equivalent).  
- Our custom processors appear and run correctly in the NiFi UI.  

Input Flow File:

```json
[ {
  "ts" : "2026-05-05 14:55:11",
  "account_id" : "943",
  "transaction_id" : "6a9b1242-4892-11f1-b035-3a8bcd2ccadb",
  "amount" : 64,
  "lat" : 44.3568905517,
  "lon" : -0.6186160357,
  "nearest_city" : "Lagos",
  "nearest_country" : "Nigeria"
} ]
```

No changes to the K8s CR, mount, or pod are required to build this new python processor.

**Objective**  

Create a new, self-contained native Python processor named **PandasJSONTransformer** that:  
- Accepts JSON content in a FlowFile (e.g. output from TransactionGenerator).  
- Loads it into a Pandas DataFrame.  
- Using lon/lat determines distance from home (defined in script).  
- Outputs the transformed JSON on the `success` relationship.  

This is written as a complete, copy-paste-ready lesson that any engineer can drop into a new environment for immediate testing.

**Step 1: Create the New Processor File**  
Navigate to the exact directory where `TransactionGenerator.py` lives (the mounted extensions folder):  
```bash
cd ~/nifi-custom-processors   # ← adjust only if your local path is different
```

Create the new file `PandasJSONTransformer.py` with the full code below:

```bash
import json
import io
import pandas as pd
import numpy as np
from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult

class PandasJSONTransformer(FlowFileTransform):
    class Java:
        # Essential: Ensures success and failure relationships appear in NiFi
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '1.0.7-FINAL'
        description = 'An example processor using python pandas.'
        tags = ['pandas', 'poc', 'geospatial']
        dependencies = ['pandas', 'numpy'] # NiFi auto-installs these

    def __init__(self, **kwargs):
        # 'pass' is the safest initialization for this environment
        pass

    def transform(self, context, flowfile):
        content_bytes = flowfile.getContentsAsBytes()
        attributes = flowfile.getAttributes()

        # Merritt Island, FL Coordinates
        HOME_LAT, HOME_LON = 28.3181, -80.6660

        try:
            # Step 1: Handle the "Array Trap"
            # Even for single records, we wrap in a list so Pandas creates a proper DataFrame row
            raw_data = json.loads(content_bytes.decode('utf-8'))
            if not isinstance(raw_data, list):
                raw_data = [raw_data]

            df = pd.DataFrame(raw_data)

            # Step 2: Proof of Concept Math
            if 'lat' in df.columns and 'lon' in df.columns:
                df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
                df['lon'] = pd.to_numeric(df['lon'], errors='coerce')

                # Calculate Euclidean distance from Merritt Island:
                # dist = sqrt((lat1 - lat2)^2 + (lon1 - lon2)^2)
                df['dist_from_home'] = np.sqrt(
                    (df['lat'] - HOME_LAT)**2 + (df['lon'] - HOME_LON)**2
                )
                
                # Add a simple flag to show Pandas touched the data
                df['pandas_processed'] = True

            # Step 3: Output Generation
            output_json = df.to_json(orient='records', indent=None)
            
            return FlowFileTransformResult(
                relationship='success',
                contents=output_json.encode('utf-8'),
                attributes={
                    **attributes,
                    'pandas.transformed': 'true',
                    'pandas.version': pd.__version__
                }
            )

        except Exception as e:
            # Rule 3: Defensive failure routing
            return FlowFileTransformResult(
                relationship='failure',
                contents=content_bytes,
                attributes={**attributes, 'pandas.error': str(e)}
            )
```

**Step 2: Deploy & Activate (Live Environment)**  

1. Ensure the minikube mount (or equivalent) is still running:  
   ```bash
   minikube mount ~/nifi-custom-processors:/extensions --uid 10001 --gid 10001
   ```  
2. NiFi 2.0 automatically detects new/updated `.py` files in the extensions directory (usually within 10–30 seconds).  
3. When testing python changes, increment the `version` in the code (`1.0.1`) and re-save the file — this forces a clean reload.  

**Step 3: Verification in NiFi UI**  

- Open NiFi canvas.  
- Drag a new processor and search for **PandasJSONTransformer**.  
- It must appear with the exact description and version from the code.  
- Simple test flow:  
  `TransactionGenerator` → `PandasJSONTransformer`.   [Flow Definition File](https://raw.githubusercontent.com/cldr-steven-matison/NiFi-Templates/refs/heads/main/CustomPythonProcessorWithPandas.json).
- Run the flow.  
- Check output for the new columns `dist_from_home` and `pandas_processed`.

When the processor is first introduced to the canvas it will indicate dependencies are downloading before allowing you to route Success/Failure.

**Step 4: Hand-Off Framework for Any Other Environment**  

To replicate this exact processor in a different CFM environment:  
1. Place `PandasJSONTransformer.py` in the Python extensions path.  
2. Complete the Deployment Steps 1–3 above.  
3. Verify pandas are installed by NiFi.  
4. Confirm flowfile output is as expected.

Output Flow File:

```json
[ {
  "ts" : "2026-05-05 15:10:13",
  "account_id" : "487",
  "transaction_id" : "xxx84324584-4894-11f1-b035-3a8bcd2ccadb",
  "amount" : 39,
  "lat" : 48.4010217027,
  "lon" : 4.7099962916,
  "dist_from_home" : 87.7062397261,
  "pandas_processed" : true
} ]
```

**Troubleshooting**  

```bash
# Check NiFi pod logs for processor loading
kubectl logs -n cld-streaming mynifi-0 | grep -i pandas

# check pod for python extensions
kubectl exec -n cfm-streaming mynifi-0 -- ls -la /opt/nifi/nifi-current/python/extensions

```