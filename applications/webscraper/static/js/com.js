/**
 * Created by Basti on 24.05.14.
 */

function query_task_status(name) {
    var intervall_handler = window.setInterval(function(){
        $.ajax({
            url:"/ajax/get_task_status",
            type: "GET",
            dataType: "json",
            data:{name: name},
            success: function(data) {
                if (data.status != "") {
                    $.web2py.flash(data.status);
                } else {
                    window.clearInterval(intervall_handler);
                    $.web2py.hide_flash();
                }
            }
        });
    }, 2000);
}

function run(name) {
    $.ajax({
		url:"/ajax/run",
		data:{name: name},
        type: "POST",
        success: function() {
            window.location.reload();
        },
        error: function(xhr, status, error)
        {
        	window.location.href = "http://localhost/admin/default/errors/webscraper";
        }
	});
}

function delete_results(name) {
    $.ajax({
		url:"/ajax/delete_results",
		data:{name: name},
        type: "POST",
        success: function() {
            window.location.reload();
        },
        error: function(xhr, status, error)
        {
        	window.location.href = "http://localhost/admin/default/errors/webscraper";
        }
	});
}

function delete_task(name) {
    $.ajax({
		url:"/ajax/delete_task",
        type: "POST",
        data:{name: name},
        success: function() {
            window.location.href = "/";
        },
        error: function(xhr, status, error)
        {
        	window.location.href = "http://localhost/admin/default/errors/webscraper";
        }
	});
}