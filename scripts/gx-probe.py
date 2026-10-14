"""GX probe: minimal pandas validation to pin down the 1.x API."""

import shutil

import great_expectations as gx
import pandas as pd

shutil.rmtree("gx_probe", ignore_errors=True)

print("gx", gx.__version__)
context = gx.get_context(mode="file", project_root_dir="gx_probe")
print("context ok:", type(context).__name__)
ds = context.data_sources.add_pandas("probe_pandas")
asset = ds.add_dataframe_asset(name="probe_asset")
bdef = asset.add_batch_definition_whole_dataframe("probe_batch")
df = pd.DataFrame({"a": [1, 2, 3], "b": [1.5, -0.5, 2.0]})
params = {"dataframe": df}
batch = bdef.get_batch(batch_parameters=params)
suite = context.suites.add(gx.ExpectationSuite(name="probe_suite"))
suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="a"))
suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="b", min_value=0))
result = batch.validate(suite)
print("success:", result.success)
print("stats:", result.statistics)
