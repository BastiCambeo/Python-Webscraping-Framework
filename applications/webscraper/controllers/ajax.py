import json  # json support

assert auth.is_logged_in()  # all actions require login


def schedule():
    Task.get(request.vars.name).run()

def delete_results():
    return Task.get(request.vars.name).delete_results()

def export_excel():
    import xlwt  # Excel export support
    import os  # support for filesystem and path manipulation

    name = request.vars.name
    task = Task.get(name)
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

def delete_task():
    Task.get(request.vars.name).delete()

def get_task_status():
    return json.dumps({"status": Task.get(request.vars.name).status})