function createNewEmbed(src, modal){
  $.ajax(
  {
      url: src ,
      dataType: 'html',
      type: 'GET',
      success: function(data)
      {
        $("#svg-container").html(data);
        $("#svg-container svg").attr("id", "svg-doc");
        $("#svg-container svg").attr("width", "100%");
        embed = document.getElementById("svg-doc");
        svgPanZoom(embed, {
          zoomEnabled: true,
          controlIconsEnabled: true
        });
      }
  });
}

function removeEmbed(modal){
  lastEmbed = document.getElementById("svg-doc");
  svgPanZoom(lastEmbed).destroy();
  document.getElementById('svg-container').removeChild(lastEmbed);
}


function replaceSvgInModal() {
  lastEmbed = document.getElementById("svg-doc");
  console.log(lastEmbed);
  if (lastEmbed) {
    svgPanZoom(lastEmbed).destroy();
    document.getElementById('svg-container').removeChild(lastEmbed);
  }
  createNewEmbed($('#svg-url').text(), true);
}

function svg_init(modal){
  $("a.svg-view").on('click', function(){return false;});
  $(".svg-view").on('click', function(){
      if (modal){
        $('#svg-url').text($(this).attr("href"));
        $('#the-modal').modal("show");
      } else {
        removeEmbed(modal);
        createNewEmbed($(this).attr("href"), modal);
      }
      return false;
  });
  if (modal) {
    $('#the-modal').on('shown.bs.modal', function (e) {
       replaceSvgInModal();
    })
  }
}
