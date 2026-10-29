import importlib.util,json,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('app',Path('OrderThread/app.py'))
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
with tempfile.TemporaryDirectory() as folder:
 app.DB=Path(folder)/'browser.db'
 with app.db() as c:
  for record in [
   {'message':'10 blue zips','items':[{'name':'zips','variant':'blue','quantity':10,'evidence':'10 blue zips','decision':'new'}]},
   {'review_version':2,'message':'10 blue zips and 5 red zips','items':[{'name':'zips','variant':'blue','quantity':10,'evidence':'10 blue zips','decision':'repeat'},{'name':'zips','variant':'red','quantity':5,'evidence':'5 red zips','decision':'add'}]},
   {'review_version':2,'message':'10 blue zips','items':[{'name':'zips','variant':'blue','quantity':10,'evidence':'10 blue zips','decision':'new'}]}]:
   c.execute('INSERT INTO events(kind,data) VALUES (?,?)',('confirmed_proposal',json.dumps(record)))
 print('Temporary browser server on port 8876',flush=True)
 app.ThreadingHTTPServer(('127.0.0.1',8876),app.Handler).serve_forever()
