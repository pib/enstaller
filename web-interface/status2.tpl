<html dir="ltr"> 
    <head>
        <title>Status</title>
        <link rel="stylesheet" href="static/enthought.css" type="text/css" />
    </head>    
    <body class=" claro ">
        <h1><img src='static/enthought.png' height=64 width=64>EPD Installed Packages</h1>
        <table store="store1" query="{ Package: '*' }"
                clientSort="true" style="width: 100%;" rowSelector="20px">
            <thead>
                <tr>
                    <th width="300px" field="Package">
                        Package
                    </th>
                    <th width="150px">
                        Version
                    </th>
                    <th width="150px">
                        Repository
                    </th>
                </tr>
            </thead>
            <tbody>
%for i, (package, version, repo) in enumerate(items):
%  if i%2:
                <tr><td>{{package}}</td><td>{{version}}</td><td>{{repo}}</td></tr>
%  else:
                <tr class='grey'><td>{{package}}</td><td>{{version}}</td><td>{{repo}}</td></tr>
%  end
%end
            </tbody>
        </table>
    </body>
</html>
