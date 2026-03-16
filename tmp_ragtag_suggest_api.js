/*
 * suggest with item popup
 *
 * 商品検索ポップアップのsort順を変更する場合、
 * generateApiUrl(item)で生成しているAPI用URLにqueryを追加して下さい。
 * 例：&so=NEW
 *
 */


var suggestModule = (function() {

    // 各種htmlを変更する場合はこちらを編集して下さい。
    //var tmpl = _.template('<li class="search__suggest">{{label}}</li>');
    //var tmplSubtitle = _.template('<li class="search__subtitle ui-state-disabled">{{label}}</li>');
    //var tmplSearchResult = _.template('<ul class="search__result"></ul>');
    //var tmplItem = _.template('<li class="search__item"><a href="{{link}}"><img src="{{image}}" width="68" height="90" /><span class="displayBrand">{{displayBrand}}</span><span class="name">{{name}}</span><span class="price">{{price}}円(税込)</span></a></li>');
    //var tmplMore = _.template('<li class="search__more__wrap"><a class="search__more" href="{{url}}">more</a></li>');

    // 必要でしたら商品詳細へのlinkに追加したいqueryを指定してください。例：'?via=searchForm'
    //var itemDetailQuery = '';

    // サジェスト件数を指定してください。default:3
    //var suggestMaxAmount = 15;

    //var brandSuggestAmount = 10;
    //var categorySuggestAmount = 16;
    //var itemSuggestAmount = 1;

    // 商品件数を指定してください。default:3
    //var itemAmount = 3;
    var $lastSubtitle = null;

    function renderItem(ul, item) {
        if (item.type === 'subtitle') {
            $lastSubtitle = $(tmplSubtitle(item)).appendTo(ul).hide();
            return $lastSubtitle;
        }

        if (item.type !== 'contents') {
            $lastSubtitle.show();
            return $(tmpl(item)).appendTo(ul);
        }

        $suggest = $(tmpl(item)).appendTo(ul).hide();

        (function($suggest, itemData, $subtitle) {
            $.getJSON("/api/v1/sp/findById/json", {
                id: itemData.value
            }, function(data) {
                if (data == null || data.SpecialContentsInfo.sp == null) {
                    return;
                }
                var sp = data.SpecialContentsInfo.sp[itemData.value];
                if (sp == null) {
                    return;
                }
                itemData.url = sp.topUrl + '?' + additionalParam;

                $suggest.show();
                $subtitle.show();
            });
        })($suggest, item, $lastSubtitle);

        return $suggest;
    }

    function organizeArray(data) {
        var array = [];
        var dbrId = data.dbrId;
        var cateId = data.cateId;
        //var suggest = data.suggest;
        var contents = data.contents;

        if (dbrId && dbrId.length > 0) {
            array.push({
                label: "ブランド",
                value: "brand",
                type: "subtitle"
            });
            for (var i = 0; i < brandSuggestAmount && i < dbrId.length; i++) {
                array.push({
                    label: dbrId[i].label,
                    value: dbrId[i].value,
                    type: "dbr",
                    url: "/search?dbr=" + dbrId[i].value + "&" + additionalParam
                });
            }
        }
        if (cateId && cateId.length > 0) {
            array.push({
                label: "カテゴリ",
                value: "category",
                type: "subtitle"
            });
            for (var i = 0; i < categorySuggestAmount && i < cateId.length; i++) {
                var ids = cateId[i].value.split(',');
                var pcate = [];
                var cate = [];

                for (var j = 0; j < ids.length; j++) {
                    if (ids[j].length <= 2) {
                        pcate.push(ids[j]);
                    }
                    if (ids[j].length == 4) {
                        cate.push(ids[j]);
                    }
                }

                if (pcate.length > 0) {
                    pushCategory(array, cateId[i].label, pcate.join(','), additionalParam);
                } else {
                    pushCategory(array, cateId[i].label, cate.join(','), additionalParam);
                }
            }
        }
        if (contents && contents.length > 0) {
            array.push({
                label: "おすすめ",
                value: "item",
                type: "subtitle"
            });
            for (var i = 0; i < itemSuggestAmount && i < contents.length; i++) {
                var pair = contents[i].value.split(':');
                if (pair[0] == 'SP') {
                    array.push({
                        label: contents[i].label,
                        value: pair[1],
                        type: "contents",
                        url: "",
                    });
                } else if (pair[0] == 'IT') {
                    pushCategory(array, contents[i].label, pair[1], additionalParam);
                } else if (pair[0] == 'FR') {
                    array.push({
                        label: contents[i].label,
                        value: pair[1],
                        type: "suggest",
                        url: "/search?fr=" + encodeURIComponent(contents[i].label) + "&" + additionalParam
                    });
                } else {
                    array.push({
                        label: contents[i].label,
                        value: contents[i].value,
                        type: "contents",
                        url: "",
                    });
                }
            }
        }

        return array;
    }

    function selectItem(event, ui) {
        event.preventDefault();
        if (ui.item.type === 'subtitle') {
            $('.search__result').empty();
        } else {
            location.href = ui.item.url;
        }
    }

    // categoryIdの返却種別に応じたURLを生成
    function generateCategoryUrl(cateId, additionalParam) {

        if (cateId.length <= 2) {
            return "/category/" + cateId + "/?" + additionalParam;
        } else if (cateId.length == 4) {
            return "/category/" + cateId.substring(0, 2) + "/" + cateId + "/?" + additionalParam;
        } else {
            return "/search?it=" + cateId + "&" + additionalParam;
        }
    }

    // category用push
    function pushCategory(array, label, value, additionalParam) {
        array.push({
            "label": label,
            "value": value,
            "type": "cate",
            "url": generateCategoryUrl(value, additionalParam)
        });
    }

    // サジェストタイプに応じたURLを生成
    function generateApiUrl(item) {
        var url = '';

        switch (item.type) {
            case 'dbr':
                url = '/api/v1/item/search/json?limit=' + itemAmount + '&fm=none&dbr=' + item.value;
                break;

            case 'cate':
                url = '/api/v1/item/search/json?limit=' + itemAmount + '&fm=none&it=' + item.value;
                break;

            case 'suggest':
                url = '/api/v1/item/search/json?limit=' + itemAmount + '&fm=none&fr=' + encodeURIComponent(item.label);
                break;

            case 'contents':
                url = '/api/v1/item/search/json?limit=' + itemAmount + '&fm=none&areaid=' + 'sp' + item.value;
                break;
        }
        return url;
    }

    function didyoumean(term, callback) {
        function makeTerm(term) {
            return {
                term: term,
                url: "/search?fr=" + encodeURIComponent(term)
            };
        }

        $.getJSON("/search-didyoumean", {
            q: term
        }, function(data) {
            if (data.result.q) {
                var array = $.map(data.result.q, makeTerm);
                callback(array);
            }
        });
    }

    function setupSuggest(jqObj) {
        $(tmplSearchResult()).appendTo($("#search_form")); //.css("z-index", 10);
        var _data = $(jqObj).autocomplete({
            delay: 500,
            minLength: 1,
            source: function(request, response) {
                var terms = request.term.split(' ');
                var term = terms[terms.length - 1];
                $.getJSON("/search-suggest", {
                    limit: suggestMaxAmount,
                    q_word: term
                }, function(data) {
                    var array = organizeArray(data);
                    response(array);
                });
            },
            focus: function(event, ui) {
                // prevent autocomplete from updating the textbox
                event.preventDefault();
                var $searchResult = $(".search__result");
                $searchResult.empty();

                if (ui.item.type === 'subtitle') {
                    return;
                }
                var _popupTime = 200;

                //既にajax通信を行っていた場合
                if (ui.item.isPopupBefore) {
                    $searchResult.html(ui.item.html);
                    var _timeoutId = setTimeout(function() {
                        $searchResult.fadeIn(100);
                        //$searchResult.addClass("open");
                    }, _popupTime);
                    $searchResult.data("timeoutId", _timeoutId);
                } else {
                    if (ui.item.loading) {
                        return false;
                    }
                    ui.item.loading = true;
                    $.ajax({
                        type: "GET",
                        url: generateApiUrl(ui.item),
                        dataType: "json",
                        success: popupItemSuccess($searchResult, _popupTime, tmplItem, tmplMore, itemDetailQuery, ui.item)
                    });
                }

                /*
                $("#search_form_wrapper").on("blur mouseleave", '.search__suggest', 
                	function() {
                		var $searchResult = $(".search__result");
                		clearTimeout($searchResult.data("timeoutId"));
                		$searchResult.animate({width:'hide'},100);
                	}
                );
                */

                $("#search_form_wrapper").on({
                    "mouseenter": function() {
                        $(this).show();
                    },
                    "mouseleave": function() {
                        $(this).animate({ width: 'hide' }, 100);
                    }
                }, '.search__result');

            },
            select: selectItem,
            activate: function(e, ui) {
                ui.item.loading = false;
            },
            close: function() {
                var $searchResult = $(".search__result");
                clearTimeout($searchResult.data("timeoutId"));
                setTimeout(function() {
                    $(".search__result").animate({ width: 'hide' }, 100);
                }, 200);
            }
        }).data("ui-autocomplete");
        if (_data) {
            _data._renderItem = renderItem;
        }
    };
    return {
        setup: setupSuggest,
        didyoumean: didyoumean
    };
})();

//calback関数
var popupItemSuccess = function($searchResult, _popupTime, tmplItem, tmplMore, itemDetailQuery, item) {
    return function(json) {

        // flag for cache
        item.isPopupBefore = true;
        if (json.itemSearchInfoXML.rcd != 200 || json.itemSearchInfoXML.itemSearchInfo.totalHit == 0) {
            return;
        }

        item.html = "";

        var itemList = json.itemSearchInfoXML.itemSearchInfo.itL;
        for (var i = 0; i < itemList.length; i++) {
            var price;
            if (itemList[i].it.spl != itemList[i].it.sph) {
                price = itemList[i].it.spl + '～' + itemList[i].it.sph;
            } else {
                price = itemList[i].it.spl;
            }
            //変数定義
            var itemInfo = {
                "image": (typeof imageBaseUrl !== 'undefined' ? imageBaseUrl : '') + itemList[i].it.img.replace("_pz_", "_mz_"),
                "name": itemList[i].it.itNm,
                "price": price,
                "link": itemList[i].it.itUrl + itemDetailQuery,
                "displayBrand": itemList[i].it.dBrNm
            };
            //変数適応
            var compiled = tmplItem(itemInfo);
            //商品情報追加
            item.html += compiled;
        }

        // もっとみる
        item.html += tmplMore(item);

        //タイマーセット
        var _timerId = setTimeout(function() {
            $searchResult.fadeIn(100);
            //$searchResult.addClass("open");
        }, 0);
        $searchResult.data("timeoutId", _timerId);

        $searchResult.html(item.html);
    }
}

$(function() {
    suggestModule.setup("#keywordtext,.search-suggest");
});
