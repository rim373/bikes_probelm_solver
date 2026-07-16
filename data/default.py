# Default instance loaded by the pipeline.
# This project runs ONLY on real Velo'v (Lyon) data from the database.
from data.data_velov import (
    instance_name,
    instance_id,
    instance_desc,
    n,
    m,
    param_mp,
    param_rp,
)
try:
    from data.data_velov import param_rp_full
except ImportError:
    pass
