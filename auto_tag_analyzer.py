import re
import json
import os
from typing import List, Dict, Set, Tuple
from PyQt5.QtCore import QSettings

class AutoTagAnalyzer:
    """
    AI生成画像のプロンプトを解析して自動タグを生成するシステム
    """
    
    def __init__(self):
        self.settings = QSettings("MyCompany", "ImageViewerApp")
        self.load_default_rules()
    
    def load_default_rules(self):
        """デフォルトのタグマッピングルールを読み込み"""
        
        # カテゴリベースのタグマッピング
        self.category_rules = {
            # 人物・キャラクター
            "人物": {
                "keywords": ["1girl", "1boy", "2girls", "2boys", "girl", "boy", "woman", "man", 
                           "solo", "multiple", "twins", "sisters", "brothers"],
                "tags": ["人物", "キャラクター"]
            },
            "表情": {
                "keywords": ["smile", "smiling", "happy", "sad", "angry", "surprised", "crying",
                           "laughing", "serious", "wink", "blush", "embarrassed"],
                "tags": ["表情"]
            },
            
            # 衣装・ファッション  
            "衣装": {
                "keywords": ["dress", "shirt", "skirt", "pants", "jacket", "coat", "uniform", 
                           "kimono", "swimsuit", "bikini", "lingerie", "armor", "cosplay"],
                "tags": ["衣装", "ファッション"]
            },
            "制服": {
                "keywords": ["school_uniform", "sailor_uniform", "blazer", "tie", "ribbon"],
                "tags": ["制服", "学校"]
            },
            
            # 髪・外見
            "髪色": {
                "keywords": ["blonde_hair", "brown_hair", "black_hair", "white_hair", "silver_hair",
                           "red_hair", "blue_hair", "green_hair", "pink_hair", "purple_hair"],
                "tags": ["髪色"]
            },
            "髪型": {
                "keywords": ["long_hair", "short_hair", "twintails", "ponytail", "braids", 
                           "curly_hair", "straight_hair", "wavy_hair"],
                "tags": ["髪型"]
            },
            
            # 背景・環境
            "屋外": {
                "keywords": ["outdoor", "outside", "park", "street", "road", "beach", "forest",
                           "mountain", "sky", "clouds", "sunset", "sunrise", "nature"],
                "tags": ["屋外", "自然"]
            },
            "屋内": {
                "keywords": ["indoor", "inside", "room", "bedroom", "kitchen", "bathroom", 
                           "living_room", "office", "classroom", "library"],
                "tags": ["屋内", "建物"]
            },
            "学校": {
                "keywords": ["school", "classroom", "library", "gymnasium", "cafeteria", 
                           "hallway", "stairs", "rooftop"],
                "tags": ["学校", "教育"]
            },
            
            # アートスタイル
            "アニメ": {
                "keywords": ["anime", "manga", "cartoon", "2d", "cel_shading", "flat_colors"],
                "tags": ["アニメ", "二次元"]
            },
            "リアル": {
                "keywords": ["realistic", "photorealistic", "3d", "cgi", "photography", "portrait"],
                "tags": ["リアル", "写実的"]
            },
            
            # 品質・技術（コメントアウト - 不要なため）
            # "高品質": {
            #     "keywords": ["masterpiece", "best_quality", "high_quality", "amazing_quality",
            #                "very_aesthetic", "absurdres", "ultra_detailed", "extremely_detailed"],
            #     "tags": ["高品質", "傑作"]
            # },
            "AI生成": {
                "keywords": ["stable_diffusion", "midjourney", "dall-e", "ai_generated", 
                           "diffusion", "generated"],
                "tags": ["AI生成", "人工知能"]
            },
            
            # 時間・季節
            "季節": {
                "keywords": ["spring", "summer", "autumn", "winter", "cherry_blossoms", 
                           "snow", "rain", "sunny"],
                "tags": ["季節"]
            },
            "時間": {
                "keywords": ["morning", "noon", "evening", "night", "midnight", "dawn", "dusk"],
                "tags": ["時間帯"]
            },
            
            # 動作・ポーズ
            "ポーズ": {
                "keywords": ["standing", "sitting", "lying", "walking", "running", "jumping",
                           "dancing", "sleeping", "waving", "pointing"],
                "tags": ["ポーズ", "動作"]
            },
            
            # 成人向け（R-18）
            "成人向け": {
                "keywords": ["nsfw", "hetero", "sex", "nude", "naked", "orgasm", "moaning"],
                "tags": ["成人向け", "R-18"]
            },
            "性的ポーズ": {
                "keywords": ["cowgirl position", "straddling", "sit astride", "doggy style"],
                "tags": ["性的ポーズ", "体位"]
            },
            "身体": {
                "keywords": ["breasts", "large breasts", "small breasts", "chest", "nipples"],
                "tags": ["身体", "体型"]
            }
        }
        
        # 除外するべきキーワード（タグにしない方が良いもの）
        self.exclude_keywords = {
            # 技術的パラメータ
            "steps", "cfg", "scale", "sampler", "seed", "width", "height", "clip", "skip",
            "eta", "ddim", "euler", "heun", "dpm", "lms", "break",
            
            # ソース・品質スコア系（Stable Diffusion等）
            "source_pony", "source_furrya", "source_cartoon", "source_anime",
            "score_1", "score_2", "score_3", "score_4_up", "score_5_up", 
            "score_6_up", "score_7a_up", "score_8_up", "score_9",
            
            # 品質制御（ポジティブ系）
            "masterpiece", "best_quality", "good_quality", "amazing_quality", 
            "very_aesthetic", "absurdres", "ultra_detailed", "extremely_detailed",
            "high_quality", "best quality", "good quality", "amazing quality",
            
            # 品質関連（日本語）
            "高品質", "傑作", "最高品質", "良質", "素晴らしい品質",
            
            # 品質制御（ネガティブ系）
            "worst_quality", "low_quality", "normal_quality", "bad_anatomy", "bad_hands",
            "missing_fingers", "extra_fingers", "blurry", "jpeg_artifacts",
            
            # 基本的すぎる分類
            "1girl", "1boy", "solo", "nsfw", "hetero",
            
            # アダルト系基本
            "penis",
            
            # 重み指定と数値
            "1.1", "1.2", "1.3", "1.4", "1.5", "0.8", "0.9", "2.0",
            
            # 制御文字・空文字・改行関連
            "", " ", "\n", "\r", "\t", "\\n", "\\r", "\\t",
            "\nbreak", "\nbreak\n", "break\n", "\n\n", "\n\n\n", "\n\n\n\n",
            
            # 汎用すぎるもの
            "very", "extremely", "highly", "ultra", "super", "mega"
        }
        
        # 除外すべきプレフィックス
        self.exclude_prefixes = [
            "source_",    # source_pony, source_anime等
            "score_",     # score_9, score_8_up等  
            "lora:",      # LoRA指定
            "break ",     # BREAK区切り
            ":",          # 重み指定の残骸
        ]
        
        # 除外すべきアダルト系キーワード（オプション）
        self.adult_keywords = {
            "nsfw", "hetero", "vaginal", "penis", "orgasm", "moaning", "vulgarity",
            "cowgirl position", "straddling", "sit astride", "milking a penis",
            "sex", "nude", "naked", "breasts", "large breasts", "nipples", "pussy", "ass",
            "anal", "oral", "blowjob", "cumshot", "cum", "vaginal penis", "trembling",
            "milking", "ceiling"  # 文脈的に不適切なもの
        }
    
    def analyze_prompt_data(self, prompt_data: Dict) -> Set[str]:
        """
        シンプルなルールベースでプロンプトを解析してタグを生成
        
        Args:
            prompt_data: parse_prompt_dataの結果
            
        Returns:
            推奨タグのセット
        """
        suggested_tags = set()
        
        # プロンプトテキストを統合（Hires promptは除外）
        all_text = ""
        
        # プロンプトデータの型安全処理
        prompt = prompt_data.get("prompt")
        if prompt and isinstance(prompt, str):
            all_text += prompt + " "
        elif prompt:
            print(f"[警告] プロンプトが文字列でない: {type(prompt)} - {prompt}")
            
        negative_prompt = prompt_data.get("negative_prompt") 
        if negative_prompt and isinstance(negative_prompt, str):
            all_text += negative_prompt + " "
        elif negative_prompt:
            print(f"[警告] ネガティブプロンプトが文字列でない: {type(negative_prompt)} - {negative_prompt}")
            
        # hires_prompt は解析対象から除外
        
        # テキストを小文字に変換して解析
        text_lower = all_text.lower()
        
        # ユーザー設定のマッピングルールを適用（長いキーワード優先）
        mapping_rules = self.load_mapping_rules()
        
        # キーワードを長さ順でソート（長い順）
        sorted_keywords = sorted(mapping_rules.keys(), key=len, reverse=True)
        
        matched_keywords = set()
        for keyword in sorted_keywords:
            # キーワードの型安全チェック
            if not isinstance(keyword, str):
                print(f"[警告] キーワードが文字列でない: {type(keyword)} - {keyword}")
                continue
                
            keyword_lower = keyword.lower()
            if self._keyword_matches(keyword_lower, text_lower):
                # より長いキーワードが既にマッチしている場合はスキップ
                if not any(keyword_lower in longer_keyword for longer_keyword in matched_keywords):
                    suggested_tags.update(mapping_rules[keyword])
                    matched_keywords.add(keyword_lower)
        
        return suggested_tags
    
    def _keyword_matches(self, keyword: str, text: str) -> bool:
        """キーワードがテキスト中に存在するかをチェック（単語境界考慮）"""
        # 型安全チェック
        if not isinstance(keyword, str) or not isinstance(text, str):
            print(f"[警告] _keyword_matches: 非文字列引数 - keyword: {type(keyword)}, text: {type(text)}")
            return False
            
        # アンダースコアを含むキーワードは完全一致
        if "_" in keyword:
            return keyword in text
        
        # 通常のキーワードは単語境界でマッチ
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text))
    
    def _extract_individual_tags(self, text: str) -> Set[str]:
        """個別の有用なキーワードをタグとして抽出（カンマ区切り対応改良版）"""
        individual_tags = set()
        
        # BREAKキーワードを区切り文字として扱う（大文字小文字問わず）
        text = re.sub(r'\bBREAK\b', ',', text, flags=re.IGNORECASE)
        
        # 改行文字も含めて区切り文字として処理
        text = re.sub(r'[\r\n]+', ',', text)
        
        # カンマ区切りでキーワードを分割
        keywords = re.split(r'[,\n]+', text)
        
        for keyword in keywords:
            keyword = keyword.strip()
            
            if not keyword:
                continue
            
            # 重み指定を除去: (word:1.2) -> word, <lora:...> も除去
            keyword = re.sub(r'\([^)]*:([\d.]+)\)', r'', keyword)
            keyword = re.sub(r'<[^>]*>', '', keyword)
            keyword = re.sub(r'[(){}[\]<>]', '', keyword).strip()
            
            # 改行文字、制御文字、特殊文字を徹底除去
            keyword = re.sub(r'[\r\n\t\f\v]', '', keyword)
            keyword = re.sub(r'\\n', '', keyword)  # エスケープされた改行も除去
            keyword = keyword.strip()
            
            # さらに重み指定の残骸を除去
            if ':' in keyword:
                parts = keyword.split(':')
                # 最初の部分が有効なキーワードの場合のみ採用
                if len(parts[0].strip()) >= 2:
                    keyword = parts[0].strip()
                else:
                    continue
            
            # 基本的な除外チェック
            if len(keyword) < 2 or len(keyword) > 50 or keyword.isdigit():
                continue
            
            keyword_lower = keyword.lower()
            
            # 除外キーワードチェック（デフォルト + カスタム）
            all_exclude = self.get_all_exclude_keywords()
            if keyword_lower in all_exclude:
                continue
            
            # 除外プレフィックスチェック
            should_exclude = False
            for prefix in self.exclude_prefixes:
                if keyword_lower.startswith(prefix):
                    should_exclude = True
                    break
            if should_exclude:
                continue
            
            # アダルトキーワードチェック（オプション・設定で制御可能）
            if self._should_exclude_adult_content():
                if keyword_lower in self.adult_keywords:
                    continue
            
            # 数値のみのキーワードを除外（重み指定の残骸）
            if re.match(r'^[\d.]+$', keyword):
                continue
            
            # 制御文字や特殊文字のみで構成されているかチェック
            if re.match(r'^[\s\n\r\t\\\|]+$', keyword):
                continue
            
            # 空文字、改行、制御文字のみのキーワードを除外
            if not keyword or keyword.isspace():
                continue
            
            # 最終的な文字種チェック（英数字、日本語、一部記号のみ許可）
            if not re.match(r'^[a-zA-Z0-9\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\s_-]+$', keyword):
                continue
            
            # 英語のキーワードを日本語に翻訳（簡易版）
            translated = self._translate_keyword(keyword)
            if translated and len(translated.strip()) >= 1 and translated.strip() not in ["", " "]:
                individual_tags.add(translated)
        
        return individual_tags
    
    def _should_exclude_adult_content(self) -> bool:
        """アダルトコンテンツを除外するかどうかの設定（デフォルト: False）"""
        # 設定で制御可能にする（将来的に）
        return self.settings.value("auto_tag_exclude_adult", False, type=bool)
    
    def _translate_keyword(self, keyword: str) -> str:
        """
        英語キーワードを日本語に翻訳（簡易辞書ベース）
        重要なもののみ翻訳、それ以外は元のまま返す
        """
        translation_dict = {
            # 基本的な単語
            "cat": "猫", "dog": "犬", "bird": "鳥", "fish": "魚",
            "flower": "花", "tree": "木", "grass": "草",
            "sun": "太陽", "moon": "月", "star": "星", 
            "water": "水", "fire": "火", "wind": "風",
            
            # 色・髪色
            "red": "赤", "blue": "青", "green": "緑", "yellow": "黄色", 
            "black": "黒", "white": "白", "pink": "ピンク", "purple": "紫",
            "blonde hair": "金髪", "brown hair": "茶髪", "black hair": "黒髪",
            "white hair": "白髪", "silver hair": "銀髪", "red hair": "赤髪",
            "blue hair": "青髪", "green hair": "緑髪", "pink hair": "ピンク髪",
            
            # 髪型
            "long hair": "ロングヘア", "short hair": "ショートヘア",
            "twintails": "ツインテール", "ponytail": "ポニーテール",
            
            # 衣装・アクセサリー
            "headphones": "ヘッドフォン", "glasses": "眼鏡", "hat": "帽子", 
            "bag": "鞄", "dress": "ドレス", "skirt": "スカート",
            "shirt": "シャツ", "jacket": "ジャケット", "coat": "コート",
            "school uniform": "制服", "sailor uniform": "セーラー服",
            "arm warmers": "アームウォーマー", "crop top": "クロップトップ",
            
            # 体の部位
            "eyes": "目", "blue eyes": "青い目", "brown eyes": "茶色い目",
            "green eyes": "緑の目", "red eyes": "赤い目",
            
            # 感情・表情
            "smile": "笑顔", "happy": "幸せ", "sad": "悲しい", "angry": "怒り", 
            "cute": "可愛い", "beautiful": "美しい", "cool": "クール",
            "light smile": "微笑み",
            
            # 品質関連は翻訳しない（除外対象のため）
            # "masterpiece": "傑作", "best_quality": "最高品質", "high_quality": "高品質",
            
            # 場所・背景
            "school": "学校", "classroom": "教室", "library": "図書館",
            "outdoor": "屋外", "indoor": "屋内", "park": "公園",
            "beach": "海辺", "forest": "森", "mountain": "山",
            "evening": "夕方", "morning": "朝", "night": "夜",
            "winter": "冬", "spring": "春", "summer": "夏", "autumn": "秋",
            "christmas": "クリスマス",
            
            # ポーズ・動作
            "standing": "立っている", "sitting": "座っている", "lying": "横になっている",
            "walking": "歩いている", "running": "走っている", "head tilt": "首をかしげる",
            "from above": "上から", "from below": "下から",
            
            # 物・アイテム
            "book": "本", "sword": "剣", "magic": "魔法", "crown": "王冠",
            "tattoo": "タトゥー", "armband": "腕章", "navel": "へそ", "midriff": "お腹",
            
            # キャラクター名（一般的なもの）
            "luka megurine": "巡音ルカ",
            
            # アダルト系（適切なタグ付けのため）
            "nsfw": "成人向け", "hetero": "異性愛", "straddling": "またがる", 
            "cowgirl position": "騎乗位", "orgasm": "絶頂", "moaning": "喘ぎ",
            "trembling": "震え", "large breasts": "巨乳", "breasts": "胸",
            "vaginal": "膣内", "ceiling": "天井", "from below": "下から",
        }
        
        # 型安全な処理
        if not isinstance(keyword, str):
            return str(keyword)
            
        return translation_dict.get(keyword.lower(), keyword)
    
    def save_custom_rules(self, rules: Dict):
        """カスタムルールを保存"""
        self.settings.setValue("auto_tag_custom_rules", rules)
    
    def load_custom_rules(self) -> Dict:
        """カスタムルールを読み込み"""
        return self.settings.value("auto_tag_custom_rules", {}, type=dict)
    
    def add_custom_rule(self, keyword: str, tags: List[str]):
        """カスタムルールを追加"""
        custom_rules = self.load_custom_rules()
        custom_rules[keyword] = tags
        self.save_custom_rules(custom_rules)
    
    def save_custom_exclude_keywords(self, exclude_keywords: List[str]):
        """カスタム除外キーワードを保存"""
        self.settings.setValue("auto_tag_custom_exclude", exclude_keywords)
    
    def load_custom_exclude_keywords(self) -> List[str]:
        """カスタム除外キーワードを読み込み"""
        return self.settings.value("auto_tag_custom_exclude", [], type=list)
    
    def add_custom_exclude_keyword(self, keyword: str):
        """カスタム除外キーワードを追加"""
        exclude_keywords = self.load_custom_exclude_keywords()
        if keyword not in exclude_keywords:
            exclude_keywords.append(keyword)
            self.save_custom_exclude_keywords(exclude_keywords)
    
    def remove_custom_exclude_keyword(self, keyword: str):
        """カスタム除外キーワードを削除"""
        exclude_keywords = self.load_custom_exclude_keywords()
        if keyword in exclude_keywords:
            exclude_keywords.remove(keyword)
            self.save_custom_exclude_keywords(exclude_keywords)
    
    def get_all_exclude_keywords(self) -> Set[str]:
        """デフォルト + カスタム除外キーワードの全セットを取得"""
        all_exclude = set(self.exclude_keywords)
        custom_exclude = self.load_custom_exclude_keywords()
        all_exclude.update(custom_exclude)
        return all_exclude
    
    # === シンプルなルールベースシステム ===
    
    def _simple_keyword_match(self, keyword: str, text: str) -> bool:
        """シンプルなキーワードマッチング（部分一致）"""
        return keyword in text
    
    def load_mapping_rules(self) -> Dict[str, List[str]]:
        """キーワード→タグのマッピングルールを読み込み"""
        default_rules = self.get_default_mapping_rules()
        raw_custom_rules = self.settings.value("auto_tag_mapping_rules", {}, type=dict)
        
        # カスタムルールの型安全処理
        custom_rules = {}
        for key, value in raw_custom_rules.items():
            # キーが文字列でない場合は文字列に変換
            if not isinstance(key, str):
                print(f"[修正] 非文字列キーを文字列に変換: {type(key)} {key} -> str")
                key = str(key)
            
            # 値がリストでない場合は処理をスキップ
            if not isinstance(value, list):
                print(f"[警告] キー '{key}' の値がリストでない: {type(value)} - スキップ")
                continue
                
            custom_rules[key] = value
        
        # デフォルトルールとカスタムルールをマージ
        all_rules = default_rules.copy()
        all_rules.update(custom_rules)
        
        return all_rules
    
    def save_mapping_rules(self, rules: Dict[str, List[str]]):
        """カスタムマッピングルールを保存"""
        self.settings.setValue("auto_tag_mapping_rules", rules)
    
    def add_mapping_rule(self, keyword: str, tags: List[str]):
        """新しいマッピングルールを追加"""
        custom_rules = self.settings.value("auto_tag_mapping_rules", {}, type=dict)
        custom_rules[keyword] = tags
        self.save_mapping_rules(custom_rules)
    
    def remove_mapping_rule(self, keyword: str):
        """マッピングルールを削除"""
        custom_rules = self.settings.value("auto_tag_mapping_rules", {}, type=dict)
        if keyword in custom_rules:
            del custom_rules[keyword]
            self.save_mapping_rules(custom_rules)
    
    def get_default_mapping_rules(self) -> Dict[str, List[str]]:
        """デフォルトのマッピングルールを取得"""
        return {
            # 髪関連 - 前髪スタイル
            "blunt bangs": ["ぱっつん"],
            "hime cut": ["姫カット"],
            "diagonal bangs": ["斜めの前髪"],
            "arched bangs": ["アーチ状の前髪"],
            "asymmetrical bangs": ["アシンメトリ"],
            "crossed bangs": ["交差した前髪"],
            "flipped bangs": ["はねた前髪"],
            "braided bangs": ["編み込み前髪"],
            "long bangs": ["長い前髪"],
            "short bangs": ["短い前髪"],
            "choppy bangs": ["シースルーバング"],
            "parted bangs": ["センター分け"],
            "double parted bangs": ["2ヶ所で分けた前髪"],
            "hair between eyes": ["両目の間の髪"],
            "center flap bangs": ["センターに垂れた前髪"],
            "swept bangs": ["流した前髪"],
            "bangs pinned back": ["ピン留め前髪"],
            "hair slicked back": ["後ろに流した髪"],
            "hair pulled back": ["後ろにまとめる"],
            "hair over eyes": ["目にかかる髪"],
            "hair over one eye": ["片目にかかる髪"],
            "hair over both eyes": ["両目にかかる髪"],
            "forelocks": ["前髪"],
            
            # 髪関連 - 長さ
            "short hair": ["ショートヘア"],
            "very short hair": ["ベリーショート"],
            "pixie cut": ["ピクシーカット"],
            "bob cut": ["ボブカット"],
            "medium hair": ["セミロング"],
            "long hair": ["ロングヘア"],
            "very long hair": ["ベリーロング"],
            "absurdly long hair": ["超ロング"],
            
            # 髪関連 - ポニーテール
            "ponytail": ["ポニーテール"],
            "high ponytail": ["ハイポニー"],
            "low ponytail": ["ローポニー"],
            "side ponytail": ["サイドポニー"],
            "braided ponytail": ["編み込みポニー"],
            
            # 髪関連 - ツインテール
            "short twin tails": ["ショートツイン"],
            "high twin tails": ["ハイツイン"],
            "low twin tails": ["ローツイン"],
            "side twin tails": ["サイドツイン"],
            "twin tails": ["ツインテール"],
            "twintails": ["ツインテール"],
            "short twintails": ["ツインテール"],
            "high twintails": ["ツインテール"],
            "low twintails": ["ツインテール"],
            "side twintails": ["ツインテール"],
            "pigtails": ["おさげ"],
            
            # 髪関連 - お団子・まとめ髪
            "bun": ["お団子"],
            "hair bun": ["ヘアバン"],
            "high bun": ["ハイバン"],
            "low bun": ["ローバン"],
            "side bun": ["サイドバン"],
            "double bun": ["ダブルバン"],
            "braided bun": ["編み込みバン"],
            
            # 髪関連 - 編み込み
            "low-braided long hair": ["低い位置で結んだ長い三つ編み"],
            "crown braid": ["クラウンブレイド"],
            "french braid": ["フレンチブレイド"],
            "single braid": ["三つ編み"],
            "twin braids": ["三つ編みツインテール"],
            "quad braids": ["四つ編み"],
            "side braids": ["両サイドに編み込み"],
            "side braid": ["サイドブレイド"],
            "braided hair rings": ["編み込みリング"],
            "braid": ["編み込み"],
            
            # 髪関連 - ハーフアップ・アレンジ
            "half updo": ["ハーフアップ"],
            "half up braid": ["ハーフアップブレイド"],
            "half up half down braid": ["ハーフアップブレイド"],
            "two side up": ["ツーサイドアップ"],
            
            # 髪関連 - 質感・スタイル
            "straight hair": ["ストレートヘア"],
            "wavy hair": ["ウェーブヘア"],
            "drill hair": ["ドリルヘア"],
            "ringlets": ["リングレット"],
            "dreadlocks": ["ドレッドロック"],
            "cornrows": ["コーンロウ"],
            
            # 髪関連 - 特殊部位
            "ahoge": ["アホ毛"],
            "dyed ahoge": ["染めアホ毛"],
            "heart ahoge": ["ハートアホ毛"],
            "ahoge wag": ["動くアホ毛"],
            "antenna hair": ["アンテナヘア"],
            "sidelocks": ["もみあげ"],
            "hair flaps": ["頭の側面から伸びる毛束"],
            "flipped hair": ["外はね"],
            "layered hair": ["レイヤード"],
            
            # 髪関連 - 髪色
            "multicolored hair": ["マルチカラー髪"],
            "black hair": ["黒髪"],
            "brown hair": ["茶髪"],
            "blonde hair": ["金髪"],
            "silver hair": ["銀髪"],
            "pink hair": ["ピンク髪"],
            "red hair": ["赤髪"],
            "blue hair": ["青髪"],
            "green hair": ["緑髪"],
            "yellow hair": ["黄髪"],
            "gray hair": ["灰髪"],
            "grey hair": ["灰髪"],
            "purple hair": ["紫髪"],
            "orange hair": ["オレンジ髪"],
            "bronze hair": ["ブロンズ髪"],
            "white hair": ["白髪"],
            
            # 胸部関連
            "flat chest": ["平らな胸"],
            "small breasts": ["小さい胸"],
            "medium breasts": ["普通の胸"],
            "large breasts": ["大きい胸"],
            "huge breasts": ["巨胸"],
            
            # 場所・背景
            "class room": ["教室"],
            "bed room": ["寝室"],
            "city": ["街"],
            "villiage": ["村"],
            "nature background": ["自然の背景"],
            "Grassland far away from the city": ["街から遠く離れた草原"],
            "pool": ["プール"],
            "ocean": ["海"],
            "garden": ["庭"],
            "rooftop": ["屋上"],
            "flower forground": ["花の前景"],
            "Metaverse": ["メタバース"],
            
            # 季節・イベント
            "hanami": ["花見"],
            "spring": ["春"],
            "summer": ["夏"],
            "autumn": ["秋"],
            "winter": ["冬"],
            "christmas": ["クリスマス"],
            "outdoors": ["屋外"],
            "indoors": ["屋内"],
            
            # 水着関連
            "bikini": ["水着", "ビキニ"],
            "o-ring bikini": ["Oリングビキニ", "水着", "ビキニ"],
            "sports bra bikini": ["水着", "ビキニ", "スポーツブラビキニ"],
            "halter bikini": ["水着", "ビキニ", "ホルタービキニ"],
            "flounce bikini": ["水着", "ビキニ", "フラウンスビキニ"],
            "school swimsuit": ["水着", "スクール水着"],
            "Racing-style swimsuit": ["水着", "レーシングスタイル水着"],
            "Rash guard": ["水着", "ラッシュガード"],
            
            # 衣装・服装
            "backless dress": ["背中開きドレス"],
            "bare shoulders": ["肩出し"],
            "black dress": ["黒ドレス"],
            "black jacket": ["黒ジャケット"],
            "black pantyhose": ["黒パンティストッキング"],
            "boots": ["ブーツ"],
            "braided boots": ["編み上げブーツ", "ブーツ"],
            "buruma": ["ブルマ"],
            "camisole": ["キャミソール"],
            "china dress": ["チャイナドレス"],
            "chinese clothes": ["中国風衣装"],
            "cleavage cutout": ["胸元カット"],
            "dress": ["ドレス"],
            "frills": ["フリル"],
            "gothic": ["ゴシック"],
            "gym uniform": ["体操服"],
            "high-heels": ["ハイヒール"],
            "high-waist skirt": ["ハイウエストスカート"],
            "knee highs": ["ニーソックス"],
            "loafers": ["ローファー"],
            "long sleeves": ["長袖"],
            "sleeves rolled up": ["袖まくり"],
            "maid": ["メイド"],
            "maid headdress": ["メイドヘッドドレス"],
            "nurse": ["ナース"],
            "nurse cap": ["ナースキャップ"],
            "pantyhose": ["パンティストッキング"],
            "pleated skirt": ["プリーツスカート"],
            "ribbed sweater": ["リブセーター"],
            "ribbon": ["リボン"],
            "school blazer uniform": ["ブレザー制服"],
            "school uniform": ["学生服"],
            "short dress": ["ショートドレス"],
            "short shorts": ["ショートパンツ"],
            "short sleeves": ["半袖"],
            "shoes": ["靴"],
            "sleeveless": ["ノースリーブ"],
            "armless": ["アームレス"],
            "sox": ["ソックス"],
            "sweater dress": ["セータードレス"],
            "thigh boots": ["ニーハイブーツ"],
            "thigh highs": ["絶対領域ソックス"],
            "thighs": ["ニーソ"],
            "tie": ["ネクタイ"],
            "track jacket": ["ジャージ上"],
            "turtleneck": ["タートルネック"],
            "virgin killer sweater": ["童貞を殺す服", "セーター"],
            "white shirt": ["白シャツ"],
            "nude": ["裸"],

            #肌
            "pale skin": ["白肌"],
            "fair skin": ["白肌"],
            "light skin": ["白肌"],
            "dark skin": ["黒肌"],
            "dark-skinned": ["黒肌"],
            "tanned skin": ["茶肌"],
            "tan skin": ["茶肌"],
            "sun-kissed skin": ["茶肌"],
            "sun-kissed": ["茶肌"],

            # 成人向け体位・行為
            "cowgirl position": ["騎乗位"],
            "wariza cowgirl position": ["騎乗位"],
            "reverse cowgirl position": ["騎乗位", "背面騎乗位"],
            "amazon position": ["騎乗位", "アマゾン体位"],
            "doggystyle": ["背後位"],
            "fellatio": ["フェラチオ"],
            "footjob": ["足コキ"],
            "handjob": ["手コキ"],
            "hug from behind": ["背後位"],
            "lie on side": ["側位"],
            "missionary position": ["正常位"],
            "paizuri": ["パイズリ"],
            "prone bone": ["寝バック"],
            "standing doggy": ["立ちバック"],
            "tentacles": ["触手"],
            "slime": ["スライム"],
        }
    
    def batch_analyze_images(self, image_paths: List[str], metadata_getter_func) -> Dict[str, List[str]]:
        """
        複数の画像に対して一括自動タグ解析を実行
        
        Args:
            image_paths: 画像パスのリスト
            metadata_getter_func: メタデータ取得用関数 (image_path) -> metadata_dict
            
        Returns:
            {image_path: [suggested_tags]} の辞書
        """
        results = {}
        
        for image_path in image_paths:
            try:
                # メタデータを取得
                metadata = metadata_getter_func(image_path)
                
                # プロンプトデータを解析（既存の解析ロジックを使用）
                prompt_data = self._parse_ai_metadata(metadata)
                
                # 自動タグを生成
                suggested_tags = self.analyze_prompt_data(prompt_data)
                
                # リストに変換（重複除去とソート）
                results[image_path] = sorted(list(suggested_tags))
                
            except Exception as e:
                print(f"自動タグ解析エラー ({image_path}): {e}")
                results[image_path] = []
        
        return results
    
    def _parse_ai_metadata(self, metadata: Dict) -> Dict:
        """
        メタデータからAI生成情報を抽出（既存のロジックを簡略化）
        """
        prompt_data = {
            "prompt": "",
            "negative_prompt": "", 
            # hires_prompt は除外
            "parameters": {}
        }
        
        # AI関連のメタデータを探す
        for key, value in metadata.items():
            if not isinstance(value, str):
                continue
            
            key_lower = key.lower()
            
            if "prompt" in key_lower and "negative" not in key_lower and "hires" not in key_lower:
                # プロンプトからもHires prompt部分を除去
                cleaned_prompt = self._remove_hires_prompt_from_text(value)
                prompt_data["prompt"] = cleaned_prompt
            elif "negative" in key_lower and "prompt" in key_lower:
                prompt_data["negative_prompt"] = value
            # hires prompt は処理対象から除外
            elif key_lower in ["parameters", "usercomment", "comment"]:
                # パラメータを解析（Hires promptを含む行は除外）
                # まずテキストからHires prompt部分を除去
                cleaned_value = self._remove_hires_prompt_from_text(value)
                
                if ":" in cleaned_value:
                    lines = cleaned_value.split('\n')
                    for line in lines:
                        if ':' in line:
                            parts = line.split(':', 1)
                            if len(parts) == 2:
                                param_key = parts[0].strip().lower()
                                param_value = parts[1].strip()
                                
                                # Hires prompt関連のパラメータも除外
                                if 'hires' not in param_key:
                                    prompt_data["parameters"][param_key] = param_value
        return prompt_data
    
    def _remove_hires_prompt_from_text(self, text: str) -> str:
        """テキストからHires prompt部分を除去"""
        if not text:
            return text
        
        import re
        
        # Hires prompt: "..." の形式を正規表現で除去
        # エスケープされた文字（\\n等）と引用符を含む文字列を処理
        pattern = r'Hires prompt:\s*"(?:[^"\\]|\\.)*"'
        cleaned_text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        # Hires negative prompt: "..." も除去  
        pattern = r'Hires negative prompt:\s*"(?:[^"\\]|\\.)*"'
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
        
        # その他のHires関連パラメータも除去
        hires_params = [
            r'Hires upscale:\s*[^\n,]*',
            r'Hires steps:\s*[^\n,]*', 
            r'Hires upscaler:\s*[^\n,]*'
        ]
        
        for pattern in hires_params:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
        
        # 余分なカンマと空白を整理
        cleaned_text = re.sub(r',\s*,', ',', cleaned_text)  # 連続したカンマを除去
        cleaned_text = re.sub(r',\s*$', '', cleaned_text, flags=re.MULTILINE)  # 行末のカンマ除去
        cleaned_text = re.sub(r'^\s*,', '', cleaned_text, flags=re.MULTILINE)  # 行頭のカンマ除去
        
        return cleaned_text.strip()

