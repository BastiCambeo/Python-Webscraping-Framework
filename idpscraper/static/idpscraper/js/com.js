/**
 * Created by Basti on 24.05.14.
 */
/// <reference path="jquery.d.ts" />
function get_cookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
var csrftoken = get_cookie('csrftoken');
var DEFAULT = function () {
};
$.ajaxSetup({
    timeout: 24 * 3600 * 1000,
    beforeSend: function (xhr, settings) {
        xhr.setRequestHeader("X-CSRFToken", csrftoken);
    }
});
function save(name, callback) {
    if (callback === void 0) { callback = DEFAULT; }
    $.ajax({
        type: "POST",
        url: "/idpscraper/save_task/" + name,
        data: $('#task_form').serialize(),
        success: callback,
        async: false
    });
}
function run(name) {
    save(name);
    $.ajax({
        type: "POST",
        url: "/idpscraper/run_task/" + name,
        success: function () {
            window.location.reload();
        }
    });
}
function export_excel(name) {
    window.location.href = "/idpscraper/export_excel/" + name + ".xls";
}
var cursor = "", has_next = true, data_blobs = [];
function load_data(name, limit, load_all) {
    var data = { name: name, cursor: cursor };
    if (typeof limit !== "undefined") {
        data["limit"] = limit;
    }
    if (typeof load_all === "undefined") {
        load_all = false;
    }
    if (!has_next) {
        saveAs(new Blob(data_blobs), "data.txt");
        $.web2py.flash("All data sucessfully loaded");
        return;
    }
    $.ajax({
        type: "POST",
        url: "/idpscraper/get_data",
        data: data,
        dataType: "json",
        success: function (data) {
            cursor = data.cursor;
            has_next = data.has_next;
            $.web2py.flash("Data is being prepared. This can take some time depending on the size of the database.");
            data_blobs.push(data.results);
            if (load_all)
                load_data(name, limit, load_all);
        }
    });
}
function test(name) {
    save(name);
    $.ajax({
        type: "GET",
        url: "/idpscraper/test_task/" + name,
        dataType: "json",
        success: function (data) {
            $.web2py.flash(data.results);
        }
    });
}
function delete_results(name) {
    if (confirm('Are you sure you want to delete all results of this task? This cannot be undone!')) {
        $.ajax({
            url: "/idpscraper/delete_results/" + name,
            type: "POST",
            success: function () {
                window.location.reload();
            }
        });
    }
}
function delete_task(name) {
    if (confirm('Are you sure you want to delete this task COMPLETELY? This cannot be undone!')) {
        $.ajax({
            url: "/idpscraper/delete_task/" + name,
            type: "POST",
            success: function () {
                window.location.href = "/";
            }
        });
    }
}
function swap_advanced() {
    /* Show Advanced elements or hide them if already shown */
    if (!window.location.hash) {
        window.location.hash = "advanced";
        $("#swap_advanced").text("Simple View");
    }
    else {
        window.location.hash = "";
        $("#swap_advanced").text("Advanced View");
    }
    apply_advanced();
}
function apply_advanced() {
    /* Apply advanced or simple view respectively */
    if (!window.location.hash) {
        $(".advanced").hide();
    }
    else {
        $(".advanced").css("display", "inline");
    }
}
function new_task() {
    /* Creates a new empty task */
    var task_name = prompt("Please enter the task name", "");
    if (task_name) {
        $.ajax({
            url: "/idpscraper/new_task",
            type: "POST",
            data: {
                name: task_name
            },
            dataType: "json",
            success: function () {
                window.location.href = "/idpscraper/task/" + task_name;
            }
        });
    }
}
function get_task(name, callback) {
    /* When the results_id selection changes, the results_properties list must be updated */
    $.ajax({
        url: "/idpscraper/get_task/" + name,
        type: "GET",
        dataType: "json",
        success: callback // function(task)
    });
}
function update_results_properties(url_number) {
    var task_name = $(".results_id").eq(url_number).val();
    get_task(task_name, function (task) {
        $(".results_properties1").eq(url_number).empty();
        $(".results_properties2").eq(url_number).empty();
        task.selectors.forEach(function (selector) {
            $(".results_properties1").eq(url_number).append("<option>" + selector.name + "</option>");
            $(".results_properties2").eq(url_number).append("<option>" + selector.name + "</option>");
        });
    });
}
function add_url_selector() {
    $("#url_selectors").append($(".url_selector").last().clone());
}
function remove_url_selector() {
    if ($(".url_selector").length > 1)
        $(".url_selector").last().remove();
}
function add_content_selector() {
    $("#content_selectors").append($(".content_selector").last().clone());
    $("input[name=selector_is_key]").last().val(parseInt($("input[name=selector_is_key]").eq(-2).val()) + 1);
}
function remove_content_selector() {
    if ($(".content_selector").length > 1)
        $(".content_selector").last().remove();
}
function console_eval(command) {
    $.ajax({
        type: "POST",
        url: "/idpscraper/run_command",
        data: { command: command },
        dataType: "json",
        success: function (data) {
            $.web2py.flash(data.results);
        }
    });
}
//# sourceMappingURL=com.js.map