/**
 * Created by Basti on 24.05.14.
 */

function query_task_status(name) {
    var intervall_handler = window.setInterval(function(){
        $.ajax({
            url:"/webscraper/ajax/get_task_status",
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

function schedule(name) {
    $.ajax({
		url:"/webscraper/ajax/schedule",
		data:{name: name},
        type: "POST",
        success: function() {
            window.location.reload();
        }
    });
}

function delete_results(name) {
    $.ajax({
		url:"/webscraper/ajax/delete_results",
		data:{name: name},
        type: "POST",
        success: function() {
            window.location.reload();
        }
	});
}

function delete_task(name) {
    $.ajax({
		url:"/webscraper/ajax/delete_task",
        type: "POST",
        data:{name: name},
        success: function() {
            window.location.href = "/";
        }
	});
}

function swap_advanced() {
    /* Show Advanced elements or hide them if already shown */

    if ($("#swap_advanced").text() == "Advanced View") {
        $(".advanced").show();
        $("#swap_advanced").text("Simple View");
    } else {
        $(".advanced").hide();
        $("#swap_advanced").text("Advanced View");
    }
}

function create_new_task() {
    /* Creates a new empty task */

    var task_name = prompt("Please enter the task name", "");

    if (task_name != null && task_name != "") {
        window.location = "/webscraper/ajax/new_task?name=" + task_name
    }
}