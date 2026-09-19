(function () {

    let deferredPrompt = null;

    function isInstallButton(button) {
        if (!button) return false;

        const id = button.id || "";
        const text = (button.innerText || button.textContent || "")
            .trim()
            .replace(/\s+/g, " ")
            .toLowerCase();

        return (
            id === "installBottomBtn" ||
            id === "installTopBtn" ||
            text === "install" ||
            text.includes("install sr connect")
        );
    }

    function hideInstallUI() {
        document
            .querySelectorAll("#installBottomBtn, #installTopBtn")
            .forEach(el => {
                el.classList.add("hidden");
                el.style.display = "none";
            });

        document
            .querySelectorAll("button")
            .forEach(button => {
                if (!isInstallButton(button)) return;

                button.classList.add("hidden");
                button.style.display = "none";

                const bar =
                    button.parentElement &&
                    button.parentElement.parentElement;

                if (bar && /install sr connect/i.test(bar.innerText || "")) {
                    bar.style.display = "none";
                }
            });
    }

    function showInstallUI() {
        document
            .querySelectorAll("#installBottomBtn, #installTopBtn")
            .forEach(el => {
                el.classList.remove("hidden");
                el.style.display = "";
            });
    }

    window.installApp = async function (event) {

        if (event) {
            event.preventDefault();
        }

        if (!deferredPrompt) {
            alert(
                "SR Connect এখনো direct install prompt-এর জন্য ready হয়নি।"
            );
            return false;
        }

        try {
            deferredPrompt.prompt();

            const result =
                await deferredPrompt.userChoice;

            deferredPrompt = null;

            console.log(
                "SR Connect install:",
                result && result.outcome
            );

            if (
                result &&
                result.outcome === "accepted"
            ) {
                hideInstallUI();
            }

        } catch (error) {
            console.error(
                "SR Connect install failed:",
                error
            );
        }

        return false;
    };

    window.addEventListener(
        "beforeinstallprompt",
        function (event) {

            event.preventDefault();

            deferredPrompt = event;

            showInstallUI();

        }
    );

    window.addEventListener(
        "appinstalled",
        function () {

            deferredPrompt = null;

            hideInstallUI();

        }
    );

    /*
     * Capture the click BEFORE Vue/HTML handlers.
     * This fixes the current SR Portal button which
     * was only closing the banner.
     */
    document.addEventListener(
        "click",
        function (event) {

            const button =
                event.target &&
                event.target.closest
                    ? event.target.closest("button")
                    : null;

            if (!isInstallButton(button)) {
                return;
            }

            if (!deferredPrompt) {
                return;
            }

            event.preventDefault();
            event.stopImmediatePropagation();

            window.installApp(event);

        },
        true
    );

})();
