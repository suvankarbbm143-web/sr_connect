(function () {
    "use strict";

    if (window.frappe && window.frappe.call) {
        return;
    }

    function getCSRFToken() {
        return (
            window.csrf_token ||
            document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ||
            ""
        );
    }

    function getMethodURL(method) {
        if (!method) {
            throw new Error("Frappe method is missing");
        }

        if (
            method.startsWith("/") ||
            method.startsWith("http://") ||
            method.startsWith("https://")
        ) {
            return method;
        }

        return "/api/method/" + method;
    }

    async function call(options, maybeCallback) {
        if (typeof options === "string") {
            options = {
                method: options
            };
        }

        options = options || {};

        const url = getMethodURL(options.method);
        const args = options.args || {};

        const headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        };

        const csrf = getCSRFToken();

        if (csrf && csrf !== "None") {
            headers["X-Frappe-CSRF-Token"] = csrf;
        }

        const response = await fetch(url, {
            method: "POST",
            credentials: "include",
            headers: headers,
            body: JSON.stringify(args)
        });

        let data = {};

        try {
            data = await response.json();
        } catch (e) {}

        if (!response.ok) {
            throw new Error(
                data?.exception ||
                data?.message ||
                ("HTTP " + response.status)
            );
        }

        const result = {
            message: data.message,
            data: data
        };

        if (typeof options.callback === "function") {
            options.callback(result);
        }

        if (typeof maybeCallback === "function") {
            maybeCallback(result);
        }

        return result;
    }

    async function xcall(method, args) {
        const result = await call({
            method: method,
            args: args || {}
        });

        return result.message;
    }

    window.frappe = window.frappe || {};

    window.frappe.call = call;
    window.frappe.xcall = xcall;

    window.frappe.session = window.frappe.session || {
        user: null
    };

    window.frappe.boot = window.frappe.boot || {
        user: null
    };

    window.frappe.csrf_token =
        getCSRFToken();

    fetch(
        "/api/method/frappe.auth.get_logged_user",
        {
            method: "GET",
            credentials: "include",
            headers: {
                "Accept": "application/json"
            }
        }
    )
    .then(function (response) {
        return response.json();
    })
    .then(function (data) {
        const user =
            data && data.message
                ? data.message
                : null;

        if (user) {
            window.frappe.session.user = user;

            window.frappe.boot.user = {
                full_name: user
            };

            window.dispatchEvent(
                new CustomEvent(
                    "sr-frappe-ready",
                    {
                        detail: {
                            user: user
                        }
                    }
                )
            );
        }
    })
    .catch(function (error) {
        console.warn(
            "SR Connect user lookup failed",
            error
        );
    });
})();
