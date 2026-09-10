/*
 SR Connect legacy portal disabled.

 The old portal used the global browser-side `frappe`
 object directly. This causes:

     frappe is not defined

 when the page is loaded outside the Desk runtime.

 The new SR Connect home page uses REST API calls instead.
*/
