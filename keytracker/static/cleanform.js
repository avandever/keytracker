var myForm = document.getElementById('cleanform')
myForm.addEventListener('submit', function () {
    var allInputs = myForm.getElementsByTagName('input');

    for (var i = 0; i < allInputs.length; i++) {
        var input = allInputs[i];

        if (input.name && !input.value) {
            input.name = '';
        }
    }
});
