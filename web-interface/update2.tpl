<html> 
<head>
  <title>Status</title>
  <link rel="stylesheet" href="static/enthought.css" type="text/css" />
</head>
<body>
  <h1>
    <img src="static/enthought.png" height="64" width="64" />
    EPD Installed Packages
  </h1>
  <form method="post"
        action="/action">
    <table style="width: 100%;">
      <thead>
        <tr>
          <th>Package</th>
          <th>Version</th>
          <th>Repository</th>
          <th>Install</th>
        </tr>
      </thead>
      <tbody>
%for color, pkg, version, repo, action in items:
        <tr style="background-color: {{color}};">
          <td>{{pkg}}</td>
          <td>{{version}}</td>
          <td>{{repo}}</td>
          <td><input type="checkbox" name="{{pkg}}" /></td>
        </tr>
%end
      </tbody>
    </table>
    <p><input type="submit" value="update"></p>
  </form>
</body>
</html>
