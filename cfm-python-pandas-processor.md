**EXECUTION PLAN: PandasCSVTransformer – NiFi 2.0 Native Python Processor with Pandas**

**Starting Point**  

In this Python Pandas lesson we are picking up where we left off with [Custom NiFi Processors with Cloudera Streaming Operators](https://cldr-steven-matison.github.io/blog/Custom-Processors-With-Cloudera-Streaming-Operators/).

Our existing working environment has:  
- `TransactionGenerator.py` is already placed in the mounted Python extensions directory.  
- The Cloudera Streaming Operators NiFi CR is applied with the live hostPath volume mount active (minikube mount or equivalent).  
- Our custom processors appear and run correctly in the NiFi UI.  


No changes to the K8s CR, mount, or pod are required to build this new python processor.

**Objective**  
Create a new, self-contained native Python processor named **PandasJSONTransformer** that:  
- Accepts CSV content in a FlowFile (e.g. output from TransactionGenerator).  
- Loads it into a Pandas DataFrame.  
- Performs realistic customer-style transformations (cleaning, type conversion, enrichment).  
- Outputs the transformed CSV on the `success` relationship.  

This plan is written as a complete, copy-paste-ready lesson that any engineer can drop into an identical Cloudera Streaming Operators environment for immediate testing.

**Step 1: Create the New Processor File**  
Navigate to the exact directory where `TransactionGenerator.py` lives (the mounted extensions folder):  
```bash
cd ~/nifi-custom-processors   # ← adjust only if your local path is different
```

Create the new file `PandasJSONTransformer.py` with the full code below:

```bash
from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
import pandas as pd
import io

class PandasJSONTransformer(FlowFileTransform):
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']

    class ProcessorDetails:
        version = '1.0.0'
        description = 'Loads JSON array of objects into Pandas DataFrame, performs cleaning + enrichment, and outputs transformed JSON'
        tags = ['pandas', 'json', 'dataframe', 'transform']
        dependencies = ['pandas']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def transform(self, context, flowfile):
        try:
            # Read entire FlowFile content as bytes
            content_bytes = flowfile.getContentsAsBytes()

            # Load JSON array of objects into Pandas DataFrame
            # (Common customer format: [{"col1": val1, "col2": val2}, ...])
            df = pd.read_json(io.BytesIO(content_bytes), orient='records')

            # ====================== CUSTOMER TRANSFORMATION LOGIC ======================
            # 1. Drop rows with any null values in key columns (configurable via code)
            df = df.dropna()

            # 2. Enforce correct data types
            if 'amount' in df.columns:
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            if 'quantity' in df.columns:
                df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

            # 3. Example enrichment / derived columns (realistic customer use case)
            if 'quantity' in df.columns and 'amount' in df.columns:
                df['total_value'] = df['quantity'] * df['amount']

            # 4. Optional filtering example (uncomment/modify as needed)
            # df = df[df['total_value'] > 0]

            # Convert DataFrame back to JSON array (same format as input)
            output_bytes = df.to_json(orient='records', indent=None).encode('utf-8')

            # Return transformed FlowFile
            return FlowFileTransformResult(
                relationship='success',
                contents=output_bytes,
                attributes={
                    'pandas.rows.processed': str(len(df)),
                    'pandas.columns': ','.join(df.columns.tolist()),
                    'pandas.transformed': 'true'
                }
            )

        except Exception as e:
            # Route errors to failure relationship with original content
            return FlowFileTransformResult(
                relationship='failure',
                contents=flowfile.getContentsAsBytes(),
                attributes={
                    **flowfile.getAttributes(),
                    'pandas.error': str(e)
                }
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
  `TransactionGenerator` → `PandasJSONTransformer` → `PutFile` (or `LogAttribute` + `UpdateAttribute`).  
- Run the flow.  
- Check output: new columns (`total_value`, etc.), cleaned data, and the added attributes.

**Step 4: Hand-Off Framework for Any Other Environment**  
To replicate this exact processor in a different Kubernetes/minikube/CFM environment:  
1. Copy the entire `~/nifi-custom-processors/` folder (or just the two `.py` files).  
2. Place `PandasJSONTransformer.py` into the same mounted Python extensions path used by your Cloudera Streaming Operators CR.  
3. Apply the identical volume mount configuration you used for TransactionGenerator.  
4. Run Steps 1–3 above.  
5. Verify pandas is auto-installed by NiFi (visible in processor logs if needed).  

**Troubleshooting (Copy-Paste Commands)**  
```bash
# Check NiFi pod logs for processor loading
kubectl logs -n cld-streaming mynifi-0 | grep -i pandas

# Force processor reload (optional)
# Edit version in PandasCSVTransformer.py → save → wait 30s
```