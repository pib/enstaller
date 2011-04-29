<html dir="ltr"> 
<head>
  <title>Status</title>
  <link rel="stylesheet" href="static/enthought.css" type="text/css" />
  <script type="text/javascript">
function createRequestObject() {
    var res;
    var browser = navigator.appName;
    if(browser == "Microsoft Internet Explorer") {
        res = new ActiveXObject("Microsoft.XMLHTTP");
    } else {
        res = new XMLHttpRequest();
    }
    return res;
}

var http = createRequestObject();

function handleResponse() {
    if(http.readyState == 4) {
        var response = http.responseText;
	if(response) {
            document.getElementById('ajaxout').innerHTML = response;
        }
    }
}

function sxf(caller) {
    http.open('get', 'action/' + caller.id);
    http.onreadystatechange = handleResponse;
    http.send(null);
}
  </script>
</head>
<body class=" claro ">
  <h1>
    <img src="static/enthought.png" height="64" width="64" />
    EPD Installed Packages
  </h1>
  <table style="width: 100%;">
    <thead>
      <tr>
        <th>Package</th>
        <th>Version</th>
        <th>Repository</th>
        <th>Action</th>
      </tr>
    </thead>
    <tbody>
%for cls, package, version, repo, action in items:
      <tr style="background-color: {{cls}};">
        <td>{{package}}</td>
        <td>{{version}}</td>
        <td>{{repo}}</td>
        <td>{{!action}}</td>
      </tr>
%end
    </tbody>
  </table>
</body>
</html>
