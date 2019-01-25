<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet
  version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:template match="statistics">
    <html>
      <head>
        <xsl:comment>
          <![CDATA[if lt IE 9]><script src="excanvas.js"></script><![endif]]]>
        </xsl:comment>
        <meta http-equiv="X-UA-Compatible" content="IE=9" />
        <title>AROW Send on <xsl:value-of select="/statistics/system/hostname"/> (<xsl:value-of select="/statistics/system/version"/>)</title>
        <style type="text/css">
          body { font: 10pt helvetica; background-color: white; }
          table td {
          background-color: #f0f0d0;
          padding: 4px; margin: 4px;
          }
          div {
          margin: 5px;
          }
          .running {
          background: #c0ffc0;
          }
          .failed {
          background: #ffc0c0;
          }
          .graph {
          border: 1px solid black;
          position: relative;
          top: 10px;
          height: 300px;
          width: 300px;
          margin-left: 4em;
          }
        </style>
      </head>
      <body onload="run()">
        <h1>AROW</h1>

        <div>
<!-- 
          <p>
            <a href="routing">LIID information</a>
          </p>
-->
          <h2>Setup</h2>
    
          <table id="setup">

            <tr>
              <th>Address</th>
              <th>Port</th>
              <th>UDP Port</th>
              <th>TCP Port</th>-->
              <th>Heartbeat</th>
            </tr>

          </table>

          <div id="no_setup">
            <i>No inputs have been specified.</i>
          </div>

        </div>

        <div>
          <h2>Modes</h2>
          <table id="modes">
          </table>
          <div id="no_outputs">
            <i>No modes have been specified.</i>
          </div>

          <!--
                <p><i style="font-size: 8pt">Note: NHIS 1.1 inputs / outputs PDU 
             counts may not match due to way START
             PDUs are handled.</i></p>
          -->

        </div>
<!--
        <div>

           <h2>top 5 s</h2>
    
          <table id="active">

            <tr>
              <th>LIID</th>
              <th>Rate</th>
            </tr>

          </table>

          <p>
            <a href="routing">LIID information</a>
          </p>

        </div>
-->
 
        <div>
          <h2>Throughput</h2>
          <div>
            Graph Options
            <select id="ddGraphTime">
              <option value ="200s">200 S </option>
              <option value ="15m">15 m </option>
              <option value ="1hour">1 Hour </option>
              <option value ="6hour"> 6 Hours </option>
              <option value ="24hour">24 Hours </option>
            </select>
            <select id="ddGraphMax">
              <option value ="1M">1 Mbps </option>
              <option value ="10M">10 Mbps </option>
              <option value ="100M">100 Mbps </option>
              <option value ="500M">500 Mbps </option>
              <option value ="1000M">1Gbps </option>
            </select>
          </div>
          <div>
            <div style="float: left; position: relative; margin-left: 40px">
              <div>
                <center>
                  <b>Average Transfer data rate ( 5 secs) (<span id="input-data-rate"></span>Mb/s)</b>
                </center>
              </div>
              <canvas id ="ipcvs" width="400" height="340">[No canvas support]</canvas>
            </div>
          </div>
        </div>

        <script type="text/javascript" src="jquery.js"> </script>
        <script type="text/javascript" src="RGraph.common.core.js"> </script>
        <script type="text/javascript" src="RGraph.bar.js"> </script>
        <script type="text/javascript" src="RGraph.drawing.xaxis.js"> </script>
        <script>
          $(document).ready(function()
          {
          run();
          //console.log("doc loaded");
          }
          );
        </script>
        <script language="JavaScript">
<![CDATA[

var num_inputs = 0;
var num_outputs = 0;
var max_active = 5;
//-----------------------------------------------------------------------
function xmlrpc()
	{
    var req = null;
    if (window.XMLHttpRequest)
    	{
	  	req = new XMLHttpRequest;
		}
	else 
		if (window.ActiveXObject)
			{
	  		req = new ActiveXObject("Microsoft.XMLHTTP")
			}
		return req
    } 
//-------------------------------------------------------------------------
 function by_data(a, b)
 	{
    if (a.data < b.data) return 1;
    if (a.data < b.data) return -1;
    return 0;
    }
//-----------------------------------------------------------------------
function by_description(a, b)
	{
    if (a.description < b.description) return -1;
    if (a.description < b.description) return 1;
    return 0;
    }
//----------------------------------------------------------------------
function get_elt(xml, e)
	{
    return xml.getElementsByTagName(e)[0].firstChild.data;
    }
//-------------------------------------------------------------------------
 function delete_children(id)
 	{
    var elt;
    elt = document.getElementById(id);
    while (elt.hasChildNodes())
  		elt.removeChild(elt.firstChild);
    }
//----------------------------------------------------------------------
function run()
	{
    /*for (var i = 0; i < max_active; i++)
    	{
	  	var row = document.getElementById("active").insertRow(i + 1);
        row.insertCell(0);
        row.insertCell(1);
        }
*/
     //console.log("here")
  document.getElementById("ddGraphTime").selectedIndex=0;//set initial dropdown box positions
	document.getElementById("ddGraphMax").selectedIndex=4;  
  update_io();
     //setTimeout(update_stats, 1000);
     setTimeout(update_stats, 0);
     }
//----------------------------------------------------------------------------
function update_io()
	{
	var sreq = xmlrpc();
	sreq.open("GET", ".", false)
	sreq.send("");

	if (sreq.status != 200)
		{
	  	alert("Map failed.");
	  	return;
		}
   	var xml = sreq.responseXML;
    var setup = Array();
    var elts = xml.getElementsByTagName("input");
        
    if (elts.length == 0)
    	{
        document.getElementById("setup").style["visibility"] = "hidden";
        document.getElementById("setup").style["display"] = "none";
        document.getElementById("no_setup").style["visibility"] = "visible";
        document.getElementById("no_setup").style["display"] = "block";
        }
    else
    	{
        document.getElementById("no_setup").style["visibility"] = "hidden";
        document.getElementById("no_setup").style["display"] = "none";
        document.getElementById("setup").style["visibility"] = "visible";
        document.getElementById("setup").style["display"] = "block";
		for(var i = 0; i < elts.length; i++)
			{
	   	 	var j = {}
	    	j.inaddress = get_elt(elts[i], "inaddress");
	    	j.port = get_elt(elts[i], "port");
	    	j.udpport = get_elt(elts[i], "udpport");
	    	j.tcpport = get_elt(elts[i], "tcpport");
	    	j.status = get_elt(elts[i], "status");
	    	try
	    		{
	      		j.error = get_elt(elts[i], "error");
	    		}
	    	catch (e)
	     		{
	    		}
	    	setup.push(j);
	  		}
		}

	var modes = Array();
    var elts = xml.getElementsByTagName("mode");

    if (elts.length == 0)
    	{
        document.getElementById("modes").style["visibility"] = "hidden";
        document.getElementById("modes").style["display"] = "none";
        document.getElementById("no_outputs").style["visibility"] = "visible";
        document.getElementById("no_outputs").style["display"] = "block";
        }
    else
        {
        document.getElementById("no_outputs").style["visibility"] = "hidden";
        document.getElementById("no_outputs").style["display"] = "none";
        document.getElementById("modes").style["visibility"] = "visible";
        document.getElementById("modes").style["display"] = "block";
	  	for(var i = 0; i < elts.length; i++)
	  		{
	    	var j = {}
	    	j.recovery = get_elt(elts[i], "recovery");
	    	j.debug = get_elt(elts[i], "debug");
        j.flowrate = get_elt(elts[i], "flowrate");
	    	j.loop = get_elt(elts[i], "loop");
	    	j.pause = get_elt(elts[i], "pause");
	    	//j.status = get_elt(elts[i], "status");
	    	try {
	      	j.error = get_elt(elts[i], "error");
	    		}
	    	catch (e) {
	    		}
	    	modes.push(j);
	  		}
        }

    setup.sort(by_description);  
    modes.sort(by_description);
    update_setup(setup);
    update_modes(modes);
    setTimeout(update_io, 5000);
    }
//-------------------------------------------------------------------------------------
function update_setup(data)
	{
    var r = [];
	var k = -1;
    var elt = document.getElementById("setup");
    r[++k] = "<tr><th>Address</th><th>Port</th><th>UDP Port</th><th>TCP Port</th> <th>Heartbeat</th></tr>";
    for(var i = 0; i < data.length; i++)
    	{
        var j = data[i];
        msg = j.status;
	    if (j.error)
        	msg += ": " + j.error;
        r[++k] = "<tr><td>";
        r[++k] = j.inaddress;
        r[++k] = "</td><td>"; 
        r[++k] = j.port;
        r[++k] = "</td><td>";
        r[++k] = j.udpport;
        r[++k] = "</td><td>";
        r[++k] = j.tcpport;
        r[++k] = '</td><td class="'
        r[++k] = j.status.toLowerCase();
        r[++k] = '">';
        r[++k] = msg;
        r[++k] = "</td>";
        }
    $(elt).empty().html(r.join(""));
    }
//--------------------------------------------------------------------------------
 function update_modes(data)
 	{
    //return // knock it out for now
    var r = [];
    var k = -1;
    var elt = document.getElementById("modes");
    r[++k] = "<tr><th>Recovery</th><th>Debug</th><th>Flow Limit (kbps)</th><th>Loop</th><th>Pause</th></tr>";
    for(var i = 0; i < data.length; i++)
    	{
        var j = data[i];
        msg = j.status;
        if (j.error)
	        msg += ": " + j.error;
        r[++k] = "<tr><td>";
        r[++k] = j.recovery;
        r[++k] = "</td><td>"; 
        r[++k] = j.debug;
        r[++k] = "</td><td>";
        r[++k] = j.flowrate;
        r[++k] = "</td><td>";
        r[++k] = j.loop;
        r[++k] = "</td><td>";
        r[++k] = j.pause;
        //r[++k] = '</td><td class="'
        //r[++k] = j.status.toLowerCase();
        //r[++k] = '">';
        //r[++k] = msg;
        r[++k] = "</td>";
        }
    $(elt).html(r.join(""));
    }
//----------------------------------------------------------------------------------------
function update_liids(data)
	{
    var elt = document.getElementById("active");
    while (data.length < 5)
    	{
        var j = {}
        j.liid = '-';
        j.data = '-';
        data.push(j);
        }
    for(var i = 0; i < 5; i++)
    	{
        var row = elt.rows[i + 1];
        for(var j = 0; j < row.cells.length; j++)
            while (row.cells[j].firstChild)
              row.cells[j].removeChild(row.cells[j].firstChild);

         var j = data[i];
         row.cells[0].appendChild(document.createTextNode(j.liid));
         if (j.data != "-") j.data += " Mb/s";
	     	row.cells[1].appendChild(document.createTextNode(j.data));
        }
    }
//-------------------------------------------------------------------------------
function update_stats()
	{
	var sreq = xmlrpc();
	sreq.open("GET", "stats", false)
	sreq.send("");
	if (sreq.status != 200)
		{
	  	alert("Map failed.");
	  	return;
		}

  var xml = sreq.responseXML;
  var period = get_elt(xml, "period");
  var periods = get_elt(xml, "periods");
  var input_rates = {}
  var input_rate={};
  var input_ratem = {};
  var input_rateh = {};
  var e = document.getElementById("ddGraphTime");
  if(e != null){
    var timeIndex=e.selectedIndex;
    }
  switch (timeIndex){ 
   	case 0: 	xperiods=200; //200 secs
   			input_rates=input_rate;
   		break;
   		case 1: 	xperiods=15; //60 mins
   			input_rates=input_ratem;
   		break;				 
   		case 2: 	xperiods=60; //60 secs
   			input_rates=input_ratem;
   		break;
   		case 3: 	xperiods=6;
   			input_rates=input_rateh;
   		break;
   		case 4: 	xperiods=24;
   			input_rates=input_rateh;
   		break;
   		}

   
    
    var elts = xml.getElementsByTagName("input");
    //var elts = xml.getElementsByTagName("input");
    eleParse(elts,input_rate,period);
   // var current_input_rate = input_rate[(periods-1)];
   // console.log(input_rate[39])
    var eltm = xml.getElementsByTagName("inputm");
    if (eltm !=null)
    	eleParse(eltm,input_ratem,period);
    var elth = xml.getElementsByTagName("inputh");
    if (elth !=null)
    	eleParse(elth,input_rateh,period);
   
    
 //update_graph("input_rate", input_rates, period, periods);
  update_bar_graph( input_rates,  xperiods,timeIndex,'ipcvs');
//$("#input-data-rate").text(Math.floor(current_input_rate*100)/100);
	
    setTimeout(update_stats, 5000);
    //setTimeout(update_stats, period * 1000);

    }
//-----------------------------------------------------------------------------
function eleParse(indata,outdata,period)
{
   for(var i = 0; i < indata.length; i++) {
 	   var p = indata[i].attributes.getNamedItem("period").value;
       var d = indata[i].attributes.getNamedItem("data").value;
          // Convert to bits.
         //console.log(d)
        d = (d * 8);
          // Convert to megabits
        d = d / (1000000.0);
        outdata[p] = d/period;
       // console.log(d)
	}
}
//------------------------------------------------------------------------------------
function update_graph(id, data, period, periods)
	{
    
    delete_children(id);
    
    var elt = document.getElementById(id);
    for(var i in data)
    	{
        var d = data[i];
        var graph_height = 300;
        var graph_width = 300;
          // Top of graph is 1000Mb/s
        var max_mb = 1000;
	  // Convert megabits to megabits/s
        var magic_scale_factor = graph_height / max_mb;
        var high = (d * magic_scale_factor) + 0;
	
		if (high > graph_height)
			 high = graph_height;
       var bar_width = (graph_width / periods) + 0;
       var div = document.createElement("div");
       div.style["height"] = high + "px";
       div.style["width"] = bar_width + "px";
       div.style["background"] = "red";
       div.style["margin"] = "0px";
       div.style["padding"] = "0px";
       div.style["position"] = "absolute";
       div.style["left"] = (i * bar_width) + "px";
       div.style["top"] = (graph_height - high) + "px";

       elt.appendChild(div);

        }        
	}
  //------------------------------------------------------------------------------------
function update_bar_graph(data,  periods,idx, graphid)
	{
	var obj =null;
    //y axis 
    var max_mb = 50;
    var e = document.getElementById("ddGraphMax");
    if(e != null)
    	{
    	var maxIndex=e.selectedIndex;
    	switch (maxIndex)
    		{ //change the y-axis scale
   			case 0: 	max_mb=1; 
   			break;
   			case 1: 	max_mb=10;
   			break;				 
   			case 2: 	max_mb=100; 
   			break;
   			case 3: 	max_mb=500; 
   			break;
   			case 4: 	max_mb=1000; 
   			break;
  	   		}
    	}
    // x-axis
    var xdata=Array();
   
	if(idx==0)
		periods =40;//to get the xscale correct for 5 sec periods
	for (var  i=0;i<periods;i++) xdata[i]=0;//fill data with zeros
    
    //var maxperiods=periods;
	for(var i in data) {
	    var d = data[i];
	    xdata.shift();
	    xdata.push(d);
	    }
	  console.log(data);
	RGraph.clear(document.getElementById(graphid,'white'));
	//console.log(idx);
	var graph=getBarGraph(graphid,xdata,max_mb,idx,obj)
//graph.set('title','jeff')
	graph.draw();
	}
//-----------------------------------------------------------------------------//----------------------------------------------------------------------------------------
  function getBarGraph(graphid,d1,ymax,idx,obj)
	{
    var graphtitle='';
    var suffixstr ='s';
    var xmax;
    var ydec=0;
    if (ymax ==1)//1 dp if max is 1Mbps
    	ydec=1;
    
    switch (idx){
    	case 0:suffixstr ='s';
           		xmax=200;
        break;
        case 1:suffixstr ='m';
            		xmax=15;
        break;
        case 2:suffixstr ='m';
            		xmax=60;
        break;
        case 3:suffixstr ='h';
            		xmax=6;
        break;
        case 4:suffixstr ='h';
            		xmax=24;
        break;
        }
    var x50= Math.round(xmax/2);
    var x25=Math.round(xmax/4);
    var x75=Math.round(xmax*0.75); 
            
    var strxmax=xmax.toString()+suffixstr;
    var strx50=x50.toString()+suffixstr;
    var strx75=x75.toString()+suffixstr;
    var strx25=x25.toString()+suffixstr;
           // console.log(strxmax);
           
    if(!obj)
    	{
    	obj = new RGraph.Bar(graphid, d1)
                .set('gutter.left',35)
                //.set('title',graphtitle)
                .set('ymax',ymax)
                .set('scale.decimals',ydec)//set decimal point
                .set('hmargin',0)
                //.set('colors', ['Gradient(pink:red:#f33)', 'Gradient(green:#0f0)'])
                .set('colors', ['red'])
                //.set('bevel', !RGraph.ISOLD)
                .set('grouping', 'stacked')
                .set('strokestyle', 'rgba(0,0,0,0)')
                //.set('labels',[strxmax,strx75,strx50,strx25,'now'])
                //.draw();
        }
    var xaxis = new RGraph.Drawing.XAxis(graphid, obj.canvas.height - 25)
   		      .set('labels',[strxmax,strx75,strx50,strx25,'now'])
                //.set('gutter.left',0)
                //.set('gutter.right',0)
              .set('labels.position','edge')
              .set('noendtick.left','true')
              .draw();          
	return obj;
	}
  //--------------------------------------------------------------------------------
]]>

</script>

</body>
</html>

</xsl:template>

</xsl:stylesheet>

