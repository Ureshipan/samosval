(function () {
    function attachAutocomplete(input) {
        var datalistId = input.getAttribute('list');
        if (!datalistId) return;
        var datalist = document.getElementById(datalistId);
        if (!datalist) return;

        var lastQ = '';
        var timer = null;

        input.addEventListener('input', function () {
            var q = (input.value || '').trim();
            if (q === lastQ) return;
            lastQ = q;
            if (timer) {
                clearTimeout(timer);
            }
            if (!q) {
                datalist.innerHTML = '';
                return;
            }
            timer = setTimeout(function () {
                fetch('/api/users/search?q=' + encodeURIComponent(q))
                    .then(function (r) { return r.json(); })
                    .then(function (list) {
                        datalist.innerHTML = '';
                        (list || []).forEach(function (login) {
                            var opt = document.createElement('option');
                            opt.value = login;
                            datalist.appendChild(opt);
                        });
                    })
                    .catch(function () { /* ignore */ });
            }, 250);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var inputs = document.querySelectorAll('input[data-user-autocomplete="1"]');
        inputs.forEach(attachAutocomplete);
    });
})();


