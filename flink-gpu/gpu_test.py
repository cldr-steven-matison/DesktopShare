from pyflink.table import EnvironmentSettings, TableEnvironment
from pyflink.table.udf import udf
from pyflink.table.expressions import col
import torch

@udf(result_type='STRING')
def check_gpu(input_str):
    if torch.cuda.is_available():
        dev = torch.cuda.get_device_name(0)
        x = torch.randn(10, 10).cuda()
        res = torch.matmul(x, x)
        return f"GPU Active: {dev} | Compute Success: True"
    else:
        return "GPU Not Found in Worker"

def run_gpu_job():
    settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
    t_env = TableEnvironment.create(settings)

    t_env.execute_sql("""
        CREATE TABLE source (
            word STRING
        ) WITH (
            'connector' = 'datagen',
            'rows-per-second' = '1',
            'fields.word.length' = '5'
        )
    """)

    t_env.create_temporary_function("check_gpu", check_gpu)
    
    # Use the table API with explicit column expressions
    tab = t_env.from_path("source")
    tab.select(col('word'), check_gpu(col('word'))) \
       .execute().print()

if __name__ == '__main__':
    run_gpu_job()
