$( function () {
    $('table').DataTable({
        "language": {
            "url": "/static/datatables/French.json"
        }
    });

    $('.delete-user').click(function(event){
        event.preventDefault();
        var that = this;
        $('.delete-confirmation').unbind('click').click(function(){
            window.location.href = $(that).attr('href');
        });
        $('.ui.basic.modal').modal('show');
    });
});
