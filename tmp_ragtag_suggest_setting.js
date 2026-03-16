	_.templateSettings = {
		interpolate: /\{\{(.+?)\}\}/g
	};

	// 各種htmlを変更する場合はこちらを編集して下さい。
	var tmpl = _.template('<li class="search__suggest">{{label}}</li>');
	var tmplSubtitle = _.template('<li class="search__subtitle ui-state-disabled">{{label}}</li>');
	var tmplSearchResult = _.template('');
	var tmplItem = _.template('<li class="search__item"><a href="{{link}}?via=searchForm"><img src="{{image}}" width="68" height="90" /><span class="displayBrand">{{displayBrand}}</span><span class="name">{{name}}</span><span class="price">{{price}}円(税込)</span></a></li>');
	var tmplMore = _.template('<li class="search__more__wrap"><a class="search__more" href="{{url}}">more</a></li>');
	
	// 必要でしたら商品詳細へのlinkに追加したいqueryを指定してください。例：'?via=searchForm'
	var itemDetailQuery = '';

	// 検索一覧へのlinkに追加したい場合はこちらにご指定ください。
	var additionalParam = "aid=header_search&via=searchForm";
	
	// サジェストの最大件数を指定してください。
	var suggestMaxAmount = 15;

	// 各サジェストの件数をsuggestMaxAmountを上限としてご指定ください。
	var brandSuggestAmount = 3;
	var categorySuggestAmount = 3;
	var itemSuggestAmount = 3;
	
	// 商品件数を指定してください。default:3
	var itemAmount = 3;
