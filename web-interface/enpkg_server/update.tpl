<html> 
<head>
  <title>Update</title>
  <link rel="stylesheet" href="static/enthought.css" type="text/css" />
</head>
<body>
  <h1>EPD Installed Packages</h1>
  <form method="post" action="/action">
    <p><input type="submit" value="update" /></p>
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
%for cls, pkg, version, repo, checkbox in items:
        <tr class="{{cls}}">
          <td>{{pkg}}</td>
          <td>{{version}}</td>
          <td>{{repo}}</td>
    %if checkbox:
          <td><input type="checkbox" name="{{pkg}}" /></td>
    %else:
          <td></td>
    %end
        </tr>
%end
      </tbody>
    </table>
    <p><input type="submit" value="update" /></p>
  </form>
</body>
</html>
