const CACHE_NAME = "sr-connect-v1";

const APP_SHELL = [
    "/home",
    "/assets/sr_connect/manifest.json"
];


self.addEventListener(
    "install",
    event => {

        event.waitUntil(

            caches
            .open(CACHE_NAME)
            .then(
                cache =>
                    cache
                    .addAll(APP_SHELL)
                    .catch(
                        () => {}
                    )
            )
            .then(
                () =>
                    self.skipWaiting()
            )

        );

    }
);



self.addEventListener(
    "activate",
    event => {

        event.waitUntil(

            caches
            .keys()
            .then(
                keys =>

                    Promise.all(

                        keys
                        .filter(
                            k =>
                                k !== CACHE_NAME
                        )
                        .map(
                            k =>
                                caches.delete(k)
                        )

                    )

            )
            .then(
                () =>
                    self.clients.claim()
            )

        );

    }
);



self.addEventListener(
    "fetch",
    event => {

        const req =
            event.request;


        if(
            req.method !== "GET"
        )
            return;


        const url =
            new URL(
                req.url
            );


        /*
         * API CACHE করা হবে না।
         * Job status / timer / submit realtime রাখতে হবে।
         */

        if(
            url.pathname.startsWith(
                "/api/"
            )
        ){

            return;
        }


        event.respondWith(

            fetch(req)

            .then(
                response => {

                    if(
                        response
                        &&
                        response.ok
                    ){

                        const copy =
                            response.clone();


                        caches
                        .open(
                            CACHE_NAME
                        )
                        .then(
                            cache =>
                                cache.put(
                                    req,
                                    copy
                                )
                        );

                    }


                    return response;

                }
            )

            .catch(

                () =>
                    caches
                    .match(req)
                    .then(
                        cached =>
                            cached
                            ||
                            caches.match(
                                "/home"
                            )
                    )

            )

        );

    }
);
