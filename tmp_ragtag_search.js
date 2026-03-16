// ソート表示
// disable links
$(function () {
  $('.search-condition__top-wrap .current a').click(function () {
    return false;
  })
});



// initialize labels and hrefs
$(function () {
  $('.search-condition__list').children().each(function () {
    var dataHref = $(this).data('href');
    var dataKey = $(this).data('key');
    var facetLabel = '';
    var defaultValue = $(this).data('default');

    var currentValue = defaultValue;
    var regExp = new RegExp(dataKey + '=(.*?)(&|$)');
    var matchResult = dataHref.match(regExp)
    //検索クエリにパラメータが存在する場合、値を取得する。
    //存在しない場合はデフォルトとなる選択肢の値を保持する。
    if (matchResult) {
      currentValue = matchResult[1];
    }

    //element毎にhrefを設定
    $(this).find('.search_condition__dropdown-element').each(function () {
      var dataValue = $(this).data('value');
      if (dataValue == currentValue) {
        //currentクラスの付与と表示用ラベルの取得
        facetLabel = $(this).addClass('current').find('a').text();
      } else {
        //currentの選択肢以外はaタグへhref属性を設定する
        var href = '';
        if (dataHref.indexOf(dataKey + "=") > -1) {
          var replaceStr = dataHref.match('(' + dataKey + '=.*?)(&|$)')[1];
          href = dataHref.replace(new RegExp(replaceStr), dataKey + '=' + dataValue);
        } else {
          href = utilityModule.appendToUrl(dataHref, dataKey + "=" + dataValue);
        }
        $(this).children('a').attr('href', href)
      }
    });
    if(facetLabel==''){
      facetLabel = $(this).find('.search_condition__dropdown-element[data-value="' + defaultValue +'"] a').text();
    }
    $(this).find('.search-condition__label').text(facetLabel);
  })
})




// 二重価格or自動売変
$(function(){
  $('.item-detail-info__discount-sale-price-wrap').each(function(index) {
    $(this).parent('div').children('p').addClass("is-current");
  })
});



// お気に入りアイテムコールバック
var itemPage = (function($) {

  // お気に入り登録の結果コールバック
  function addFavoriteCallback(obj) {
    return function(json) {

      if (json.error) {
        var errList = json.error;
        for (var i = 0, max = errList.length; i < max; i++) {
          if (errList[i].statusCode === "402" || errList[i].statusCode === "500"  ) {
            console.log(json);
            alert("お気に入り登録に失敗しました。");
            return;
          }
          if (errList[i].statusCode === "403" ) {
            location.href="/auth?next=" + encodeURIComponent(location.href);
            return;
          }
          else{
            console.log(json);
            alert(errList[i].errorMessage);
          }
        }
      }
      if (json.statusCode === "200") {
        $("#"+ obj).find(".is-disabled").hide();
        $("#"+ obj).find(".is-active").show();
        return;
      }
      if (json.statusCode == "403") {
      location.href="/auth?next=" + encodeURIComponent(location.href);
          return;
      }
    }
  }

  // お気に入り解除の結果コールバック
  function disFavoriteCallback(obj) {
    return function(json) {

      if (json.error) {
        var errList = json.error;
        for (var i = 0, max = errList.length; i < max; i++) {
          if (errList[i].statusCode === "402" || errList[i].statusCode === "500" || errList[i].statusCode === "503" ) {
            console.log(json);
            alert("お気に入り解除に失敗しました。");
            return;
          }
          if (errList[i].statusCode === "403" ) {
            location.href="/auth?next=" + encodeURIComponent(location.href);
            return;
          }
          else{
            console.log(json);
            alert(errList[i].errorMessage);
          }
        }
      }
      if (json.statusCode === "200") {
        $("#"+ obj).find(".is-disabled").show();
        $("#"+ obj).find(".is-active").hide();
        return;
      }
    }
  }

  // お気に入り確認の結果コールバック
  function isFavoriteCallback(obj) {
    return function(json) {

      if (json.error) {
        var errList = json.error;
        for (var i = 0, max = errList.length; i < max; i++) {
          console.log(json);
          $("#"+ obj).find(".is-disabled").show();
          $("#"+ obj).find(".is-active").hide();
        }
      }
      if (json.statusCode == "200") {
        if(json.data===true){
          $("#"+ obj).find(".is-active").show();
          $("#"+ obj).find(".is-disabled").hide();
        }else{
          $("#"+ obj).find(".is-active").hide();
          $("#"+ obj).find(".is-disabled").show();
        }
      }
      if (json.statusCode == "403") {
        $("#"+ obj).find(".is-active").hide();
        $("#"+ obj).find(".is-disabled").show();
      }
    }
  }

  return {
    disFavoriteCallback:disFavoriteCallback,
    isFavoriteCallback:isFavoriteCallback,
    addFavoriteCallback:addFavoriteCallback
  }
})(jQuery);
