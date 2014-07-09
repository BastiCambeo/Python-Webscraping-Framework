import json  # json support

def delete_all_tasks():
   Task.delete_all_tasks()

def add_tasks():
    for task in Task.example_tasks():
        task.put()
        if task.period:
            task.schedule()
    redirect("/")

def run():
    Task.get_by_name(request.vars.name).schedule(repeats=1)  # run in background (own thread)

def delete_results():
    return Task.get_by_name(request.vars.name).delete_results()

@auth.requires_login()
def view_data():
    task = Task.get_by_name(request.vars.name)
    response.title = task.name
    data = task.get_results(with_title=True)
    return dict(data=data, task=task)

@auth.requires_login()
def export_excel():
    import xlwt  # Excel export support
    import os  # support for filesystem and path manipulation

    name = request.vars.name
    task = Task.get_by_name(name)
    data = task.get_results(with_title=True)
    w = xlwt.Workbook()
    ws = w.add_sheet("data")

    ## write ##
    for x, row in enumerate(data):
        for y, cell in enumerate(row):
            ws.write(x, y, uni(cell))

    ## save ##
    path = os.path.join('applications', 'webscraper', 'uploads','%s.xls' % name)
    w.save(path)
    redirect(URL('default', 'download', args="%s.xls" % name))

@auth.requires_login()
def delete_task():
    name = request.vars.name
    task = Task.get_by_name(name)
    task.delete()

def get_task_status():
    name = request.vars.name
    return json.dumps({"status": Task.get_by_name(name).status})