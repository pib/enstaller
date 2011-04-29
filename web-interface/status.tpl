<html dir="ltr"> 
    <head>
        <title>Status</title>
        <style type="text/css">
            body, html { font-family:helvetica,arial,sans-serif; font-size:90%; }
        </style>
        <script src="http://ajax.googleapis.com/ajax/libs/dojo/1.6/dojo/dojo.xd.js"
        djConfig="parseOnLoad: true">
        </script>
        <script type="text/javascript">
            dojo.require("dojox.grid.DataGrid");
            dojo.require("dojo.data.ItemFileWriteStore");
        </script>
        <link rel="stylesheet" type="text/css" href="http://ajax.googleapis.com/ajax/libs/dojo/1.6/dijit/themes/claro/claro.css" />
        <style type="text/css">
            @import "http://ajax.googleapis.com/ajax/libs/dojo/1.6/dojox/grid/resources/Grid.css";
            @import "http://ajax.googleapis.com/ajax/libs/dojo/1.6/dojox/grid/resources/claroGrid.css";
            .dojoxGrid table { margin: 0; } html, body { width: 100%; height: 100%;
            margin: 0; }
        </style>
    </head>    
    <body class=" claro ">
        <span dojoType="dojo.data.ItemFileWriteStore" jsId="store1" url="installed"></span>
        <table dojoType="dojox.grid.DataGrid" store="store1" query="{ Package: '*' }"
                clientSort="true" style="width: 100%; height: 100%;" rowSelector="20px">
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
                    <th cellType='dojox.grid.cells.Bool' editable='true'>
                        Update
                    <th>
                </tr>
            </thead>
        </table>
    </body>
</html>
