import json  # json support

assert auth.is_logged_in()  # all actions require login


def schedule():
    Task.get(request.vars.name).schedule()

def delete_results():
    return Task.get(request.vars.name).delete_results()

def export_excel():
    import xlwt  # Excel export support
    import io  # for files in memory

    name = request.vars.name
    task = Task.get(name)
    data = task.get_results(as_table=True)
    w = xlwt.Workbook()
    ws = w.add_sheet("data")

    ## write ##
    for x, row in enumerate(data):
        for y, cell in enumerate(row):
            ws.write(x, y, uni(cell))

    ## save ##
    f = io.BytesIO('%s.xls' % name)
    w.save(f)
    response.headers["Content-Type"] = "application/vnd.ms-excel"
    return f.read()

def delete_task():
    Task.get(request.vars.name).delete()

def get_task_status():
    return json.dumps({"status": Task.get(request.vars.name).status})