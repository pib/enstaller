<html> 
<head>
  <title>Update</title>
  <link rel="stylesheet" href="static/enthought.css" type="text/css" />
</head>
<body>
  <h1>EPD Installed Packages</h1>
  <form method="post" action="/action">
    <p><input type="submit" value="install" /></p>
    <table style="width: 100%;">
      <thead>
        <tr>
          <th>Package</th>
          <th>Version</th>
          <th>Available</th>
          <th>Status</th>
          <th>install</th>
        </tr>
      </thead>
      <tbody>
%for cls, name, version, a_vers, status, checkbox in items:
        <tr class="{{cls}}">
          <td>{{name}}</td>
          <td>{{version}}</td>
          <td>{{a_vers}}</td>
          <td>{{status}}</td>
    %if checkbox:
          <td><input type="checkbox" name="{{name}}" /></td>
    %else:
          <td></td>
    %end
        </tr>
%end
      </tbody>
    </table>
    <p><input type="submit" value="install" /></p>
  </form>
</body>
</html>
