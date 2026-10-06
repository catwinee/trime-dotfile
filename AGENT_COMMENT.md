# AGENT_COMMENT —— 踩坑与实现细节

**这是长文备注，不是使用说明。** 面向的读者是「要改这套配置的人 / AI 助手」，
内容是同文（Trime）的内部行为、我们踩过的坑、验证方法，以及每个决定的依据。
功能概览请看 [README.md](README.md)。

目标设备：`Honor 60 / LSA-AN00 / Android 14 / 1080×2400 @ density 480`，
同文 **3.3.12**（内置 librime **1.17.0**）。

源码依据：本文所有「源码说」都是查过的——
Trime 源码（`app/src/main/java/...`）与 librime 源码（`src/rime/gear/...`）。
行号以当时拉到的 `develop` / `master` 为准，升级后可能漂移。

## 文件

| 本地 | 手机路径（`/sdcard/Android/data/com.osfans.trime/files/rime/`） |
|---|---|
| `trime.custom.yaml` | 主配置：键盘 / 配色 / 工具栏 / style |
| `default.custom.yaml` | 方案列表 |
| `luna_pinyin.custom.yaml` | 标点映射修正 |
| `luna_pinyin_simp.custom.yaml` | 同上，给简化字方案 |
| `ref/` | 从手机拉下来的同文预设文件，**只作参考，不要改**；也是离线模拟 patch 的基线 |
| `deploy.sh` | 备份 + 推送 4 个文件 |
| `fix_punctuator.py` | 直接修补手机上已部署的 schema 产物（见下文） |
| `backup/` `pic/` | 已 gitignore：前者是 deploy 快照，后者是设计参考截图 |

```bash
./deploy.sh
```

然后在手机上：**同文 App → 主题选「預設」→ 右上角 ↻ 圆形箭头（Deploy/部署）**

### ⚠️ 「部署」和「更新配置」不是一回事

```kotlin
// MainActivity.kt：↻ 图标 = deploy
menu.item(R.string.deploy, R.drawable.ic_baseline_refresh_reversed_24) {
    viewModel.rime.launchOnReady { it.deploy() }
}
// Rime.kt
override suspend fun deploy()      { exitRime(); startRime(true)  }  // fullCheck = true  → 重建 schema
override suspend fun updateConfig() { exitRime(); startRime(false) }  // fullCheck = false → 只更新配置
```

只有 `deploy()`（fullCheck=true）会走 `WorkspaceUpdate` → `SchemaUpdate`，
也就是**会重新编译 schema**；`updateConfig()` 不会。

判断刚才那次到底跑了哪一个：

```bash
R=/sdcard/Android/data/com.osfans.trime/files/rime
adb shell ls -la $R/build/          # schema 文件的时间戳变了没有
adb shell head -12 $R/build/luna_pinyin.schema.yaml
#   __build_info.timestamps 里 luna_pinyin.custom 变成非 0 = 补丁被吃进去了
```

如果 schema 没重建，标点补丁就不会生效。这种情况用 `fix_punctuator.py`
直接改已部署的产物（立即生效，不需要部署）：

```bash
python3 fix_punctuator.py --check   # 只看命中多少处
python3 fix_punctuator.py           # 写回手机
```

---

## 踩过的四个坑

### 一、`patch:` 是「整块替换」，不是深合并

Rime 把 patch 的键当成**路径**，把该路径上的节点**整个换掉**：

```yaml
# ✗ 错：路径停在 preset_keyboards，
#     同文自带的 symbols / number / letter / mini … 18 副键盘全被冲掉
patch:
  preset_keyboards:
    default: {...}

# ✓ 对：路径精确到那一副键盘，兄弟节点不受影响
patch:
  preset_keyboards/default: {...}
  style/horizontal_gap: 4
```

两个连带结论：

1. **被替换的节点里原有字段会一起消失**。重写一副键盘时
   `width` / `height` / `lock` / `ascii_mode` 必须自己补全。
   `width` 尤其关键——它是「按键默认宽度（屏宽百分比）」，
   缺了同文算不出按键尺寸，键盘直接渲染成空白。
2. **只改一个标量就不要写它的父节点**。

`ref/trime.yaml` 里 `style:` 有 43 项、`preset_keyboards:` 有 18 副键盘、
`preset_color_schemes:` 有 37 套配色、`preset_keys:` 有 106 项；
改动后这些数量都不该变少。

### 二、按键角标默认显示 `long_click`，不是 `swipe_up`

同文渲染按键左上角那个小字时，默认取 `long_click` 的值
（预设 `{click: 'q', long_click: '!'}` 就是这么显示出 "!" 的）。
所以「上滑出 # 但键上写着 ~」这种不一致，是因为角标画的是长按值。

修法是显式指定 `label_symbol`（同文 DEX 里确认存在 `label_symbol` / `labelSymbol`）：

```yaml
- {click: 's', label_symbol: '#', swipe_up: '#'}
```

`label_symbol` 只影响显示，`long_click` 的功能仍然保留。

### 三、`Control+字母` 的预设键默认全是废的，而且 `Ctrl+C` 在本机写不进剪贴板

Trime 把 `Control+字母` 交给 `hookKeyboard` 处理，但它依赖几个**默认关闭**的开关：

```kotlin
// AppPrefs.kt:333
val hookCtrlA  = switch(R.string.hook_ctrl_a,  HOOK_CTRL_A,  false)   // 默认 false
val hookCtrlCV = switch(R.string.hook_ctrl_cv, HOOK_CTRL_CV, false)   // 默认 false
val hookCtrlZY = switch(R.string.hook_ctrl_zy, HOOK_CTRL_ZY, false)   // 默认 false
```

开关关着时 `hookKeyboard` 返回 false，键交给 Rime；而 Rime 的 `key_binder`
只在 `when: composing` 时接 `Control+a`，其余情况直接丢弃。

**所以必须先在 同文 → Virtual Keyboard 里打开**：

- `Hook Ctrl+A`（`Clear`、`select_all` 需要）
- `Hook Ctrl+C/V/X`（`copy`/`cut`/`paste` 需要）
- `Hook Ctrl+Z/Y`（`undo`/`redo` 需要）

#### `Ctrl+C` 写不进剪贴板

实测（Honor 60 / Android 14 / Trime 3.3.12）：`Control+a/x/v/z` 都正常，
**只有 `Control+c` 不往剪贴板写东西**。

- `copy` 和 `cut` 走的是同一个 `performContextMenuAction(...)`，
  同文源码里两个分支的判定条件逐字相同（都要 `hookCtrlCV` + 非空选区），
  所以差异在 Android 侧，不在配置侧。
- 一个不对称很可疑：**同文在两个地方都在 Ctrl+C 之后立刻取消选区，而 Ctrl+X 之后没有**：

```kotlin
// ① hookKeyboard 的 C 分支
ic.performContextMenuAction(android.R.id.copy).also { r -> if (r) clearTextSelection() }
// ② Rime 按键回吐路径：TrimeInputMethodService.kt:246
sendDownUpKeyEvent(keyCode, ...)
if (it.modifiers.ctrl && keyCode == KeyEvent.KEYCODE_C) clearTextSelection()
```

  很可能就是“取消选区”跑在了“写剪贴板”前面。这是 Trime 的实现问题，`trime.yaml` 改不了。

**绕法**：用两个已验证可用的原语拼一个复制：

```yaml
preset_keys/copy_via_cut: {label: 复制, text: "{Control+x}{Control+z}"}   # 剪切 + 撤销
```

⚠️ 副作用：没有选区时 `Control+x` 会被丢弃（返回 false 后交给 Rime，Rime 也没绑），
但 `{Control+z}` 仍然执行 → **会撤销上一步编辑**（可用 redo 恢复）。

其它备选：`{Control+x}{Control+v}`（无选区时会粘上旧剪贴板内容，更危险）、
或者干脆去掉 `c` 的长按，复制用 `x`（剪切）+ `v`（粘贴）两步。

---

## 键盘（26 键，4 行）

```
q w e r t y u i o p
 a s d f g h j k l
符号 z x c v b n m        ⌫
123  中英  。，     ⎵     /    ⏎
```

宽度单位是屏宽百分比，每行正好 100：

| 行 | 组成 | 合计 |
|---|---|---|
| 1 | 10 × 10 | 100 |
| 2 | 空 5 + 9 × 10 + 空 5 | 100 |
| 3 | **符号 15 + 7 × 10 + BackSpace 15** | 100 |
| 4 | **123 10 + 中英 10 + 。，10 + 空格 40 + / 10 + 回车 20** | 100 |

第 3 行 `15 \| 70 \| 15`、第 4 行 `30 \| 40 \| 30`，两侧对称。

设计取舍：

- **没有 Shift**。下滑即出大写，Shift 完全冗余。
  腾出的那 15 给了第 3 行左端的「符号」键——这既是百度 26 键的做法，
  又让 z..m 这 7 个键在 15..85 之间居中。
- **`,` 和 `.` 合并成一个键**（语燕的做法）：点击走 Rime 标点，中文下得 `。`；
  上滑出 `，`。放在空格左侧，`/` 放在空格右侧，中英紧接数字键。

## 手势

| 手势 | 行为 |
|---|---|
| 点击 | 输入字母（中文模式走拼音，英文模式直接上屏） |
| **上滑 · 第 1 行** | `1 2 3 4 5 6 7 8 9 0` |
| **上滑 · 第 2 行** | `@ # $ % & - _ + =` |
| **上滑 · 第 3 行** | `* ( ) ' " \| \` |
| **下滑 · 字母** | 对应大写字母，**直接上屏**（用内联 `commit`，见下节） |
| **长按** | **只保留 a=全选、x=剪切、c=复制、v=粘贴**，其余键无长按 |
| 左右滑 | a/s 是 ←→ 与行首行尾，h/j 是 `[` `]` `{` `}` |
| 空格 · 四向 | 上/下 = 上下一个候选（无候选时是光标上下）；左/右 = 光标左右 |
| `⌫` 上滑 | `Clear`：全选并删除，清空整个输入框 |
| `⌫` 左滑 | `Escape`：只放弃当前拼音串 |
| `符号` 上滑 | `liquid_keyboard_switch`：打开「更多」面板 |
| `/` 上滑 | `?` |

上滑、下滑、长按是同一键上的三个独立手势，互不冲突。

角标（`label_symbol`）一律等于上滑字符，所见即所得。

### 下滑大写为什么必须用内联 `commit`

第一版写的是 `swipe_down: 'Q'`，结果在中文模式下**大写字母会进入拼写区**而不是直接上屏。
原因是 Rime 的 `recognizer`：

```cpp
// librime src/rime/gear/recognizer.cc
ProcessResult Recognizer::ProcessKeyEvent(const KeyEvent& key_event) {
  int ch = key_event.keycode();
  if ((use_space_ && ch == ' ') || (ch > 0x20 && ch < 0x80)) {
    string input = ctx->input();
    input += ch;
    auto match = patterns_.GetMatch(input, ctx->composition());
    if (match.found()) {
      ctx->PushInput(ch);      // ← 把字符推进 composition，于是「进入拼写」
      return kAccepted;
    }
  }
}
```

而 schema 里正好有这么一条规则（`default.yaml` 与各 schema 都有）：

```yaml
recognizer:
  patterns:
    uppercase: "[A-Z][-_+.'0-9A-Za-z]*$"
```

大写字母命中它 → `PushInput` → 进 composition，然后要按空格才上屏。
这是 Rime 有意的设计（让你能连打 `ABC` 再一起确认），但不符合「下滑就要直接出」的诉求。

**两条死路，别走：**

| 想法 | 为什么不行 |
|---|---|
| 把 `recognizer/patterns/uppercase` 改成永不匹配 | 大写字母会落给 `express_editor` 的 `DirectCommit`，而它是 `ctx->Commit(); return kRejected;` —— **只提交 composition、不插入这个字符**，然后 `RimeProcessKey` 对 `kRejected` 返回 true，Trime 认为「已处理」直接 return，**字符被丢掉**，变成什么都不发生 |
| 设 `ascii_composer/inline_uppercase: false` | 这个开关在 **librime 1.17.0 里根本不存在**（是 master 之后才加的）。1.17.0 的 `AsciiComposer::ProcessKeyEvent` 只在 `ascii_mode` 已开时才动作，其余一律 `kNoop` |

**真正可行的做法：绕开 Rime，让 Trime 直接上屏。**
`TextKey.swipeDown` 的类型是 `KeyActionToken?`，而它的序列化器按 YAML 节点类型分流：

```kotlin
// KeyActionTokenSerializer
is YamlScalar -> KeyActionToken.Plain.serializer()   // "Q"
is YamlMap    -> KeyActionToken.Inline.serializer()  // {commit: Q, label: Q}
```

所以键上可以直接写内联动作：

```yaml
- {click: 'q', label_symbol: '1', swipe_up: '1', swipe_down: {commit: 'Q', label: 'Q'}}
```

`Inline` 的 `commit` 会走 `service.commitText("Q")` → `ic.commitText("Q", 1)`，
Android 直接把它插进输入框，不经过 Rime ✓

两个细节：

- **要带 `label`**。滑动时的预览气泡取 `getPreviewText(behavior)` → 该 action 的
  `preview ?: getLabel()`；内联 token 的 `code` 是 0，不给 label 就没有可显示的文字。
  （按键主字不受影响：`Key.getLabel()` 取的是 **click** action 的标签。）
  注意这个气泡**默认根本不会出现** —— 见下面「滑动没有预览气泡」一节。
- **代价**：`commit` 会把「正在输入的拼音」替换掉。空 composition 时完全干净；
  若在拼音中途下滑，Rime 侧的 composition 不会被清，状态会有一瞬间不同步
  （下一个按键会把它带出来）。要彻底干净就得用 `{Escape}` 先清再上屏，
  但那要写成两层预设键，不值当。

### 滑动没有预览气泡：`popupOnKeyPress` 默认关

滑动时 Trime 确实会请求预览：

```kotlin
// KeyView.kt:126
onSwipe = { direction ->
    setPressedState(true)
    showPopupPreview(direction)      // behavior = SWIPE_UP / SWIPE_DOWN / ...
}
```

但 `showPopupPreview` 的第一句就是总开关：

```kotlin
private fun showPopupPreview(behavior: KeyBehavior = KeyBehavior.CLICK) {
    if (!keyboardView.popupOnKeyPress) return      // ← 默认 false
    ...
}
```

```kotlin
// AppPrefs.kt:243
val popupOnKeyPress = switch(R.string.popup_on_key_press, POPUP_ON_KEY_PRESS, false)
```

所以**默认任何手势（点击、长按、四向滑动）都不会弹气泡**。

想打开：同文 → **Virtual Keyboard** → **「按键时弹出显示字符」**
（英文界面 `Popup on key press`）。

- 打开后滑动会弹出该方向 action 的 `label` —— 这就是内联 token 要带 `label` 的原因
- 这个开关是**全局**的，打开后普通按键也会弹；没有「只给滑动弹」的选项
- 它是 SharedPreferences 项，`trime.yaml` 改不了，只能手动点

### 关于被删掉的长按（这些不是符号，是功能，列出来备查）

| 键 | 原长按 | 作用 | 现在的状态 |
|---|---|---|---|
| b | `Time` | 插入当前时间 | 已删 |
| n | `Insert` | 切换插入/改写模式 | 已删 |
| m | `Delete` | 删除光标后一个字符 | 已删 |
| 其余字母 | 各种符号 | `!` `@` `~` `-` `+` `\` `[` `]` `{` `}` `:` `;` `` ` `` 等 | 已删 |

想恢复某一个，把对应行的 `long_click` 加回去即可（角标由 `label_symbol` 控制，不受影响）。

底行功能键的长按也**全部去掉了**：

| 键 | 原长按 | 挪到哪了 |
|---|---|---|
| 符号 | `Keyboard_number` | 删（数字面板另有入口） |
| `/` | `?` | 改成 **上滑** 出 `?` |
| 中英 | `Menu`（方案菜单） | 删（方案菜单在工具栏 `⋯` 上） |
| 回车 | `CommitComment`（「编码」） | 删 |

所以中英文主键盘上现在只剩 **a / x / c / v** 四个长按。

## 各键盘一览

一共动了 5 副键盘（同文自带 18 副 + 新增 `editor` = 19 副）。

**中英文主键盘** `default` / `qwerty`（两副共用同一份 keys）：

```
q  w  e  r  t  y  u  i  o  p        上滑 1..0    下滑 Q..P
·  a  s  d  f  g  h  j  k  l  ·     上滑 @ # $ % & - _ + =
符号 z  x  c  v  b  n  m  ⌫         上滑 * ( ) ' " | \
123 中英 。， ⎵(40) /  ⏎             空格四向滑：候选上下 / 光标左右
```

**符号面板** `symbols`（点「符号」键切过去）：

```
1  2  3  4  5  6  7  8  9  0
~  !  @  #  $  ￥ %  ^  &  *
(  )  [  ]  「 」 、 /  :  ;
+  -  =  〈 〉 “ ” ， ？ ⌫
返回  123  。，  ⎵(50)  /   ⏎
```

符号格的 15 个变体都从长按挪到了上滑；`/` `，` `？` 三格按当初的要求
「先不要管」，仍保留原长按（`√` / 单手键盘 / 单手键盘）。

**英文面板** `letter`：

```
1 2 3 4 5 6 7 8 9 0
q w e r t y u i o p
a s d f g h j k l ;
z x c v b n m , . /
Shift 符号 中英 ⎵ ' ⌫ ⏎
```

⚠️ 这副**仍是同文原版的 40 键布局**，连全套原版长按（数字键出符号、
`a` 全选、`x` 剪切 …… 以及回车上的「编码」）都还在，和主键盘完全不同。
原因是它靠 `__include` 引用 `default`，而 `__include` 在 patch 之前就解析完了。
**要统一的话得单独重写它的 keys。**

**数字面板** `number`：

```
=⁺     1  2  3  #%
-‗     4  5  6  ¥$
*/     7  8  9  :;
/      ±  0  √² ⌫清空
返回   .， ⎵(50) /? ⏎
              ↑上标 = 上滑内容
```

**光标编辑面板** `editor`（工具栏 `⌶` 切过去，自己新写的）：

```
全选  行首  ↑   行尾  上页
剪切  ←     ↓   →    下页
复制  删除  ⌫   撤销  重做
粘贴  Esc   符号 中英  返回
```

`返回` 用自建的 `Keyboard_back`（`select: .last`），回到「上一副键盘」；
不用 `.default`，因为那是 `smartMatchKeyboard()`，从符号页打开会跳到字母键盘。

---

## 配色「纯暗／Pure Dark」

覆盖预设配色里那个叫 `default` 的方案（同文默认选中的就是它）。

| 部位 | 颜色 |
|---|---|
| 键盘底 / 整块底 | `#000000` 纯黑 |
| 按键底 | `#1a1a1e`，无边框无阴影（扁平） |
| 按键主字 / 角标 | `#e8e8ec` / `#8b8b94` |
| 候选栏 | `#0a0a0c`，候选字 `#d5d5db` |
| 编码区 | `#15151a` |
| 高亮（选中候选、开关键开态、工具栏按钮按下） | `#2f6fd0` 蓝 |

颜色写法 `0xAARRGGBB`。`0x00000000` 是全透明，`0x00` 也是透明（工具栏背景用）。

## 工具栏

`trime.yaml` 原版没有 `tool_bar:` 这一段，补上就打开了。参考同文自带「标准」主题的写法：

屏幕效果：

```
⋯  |  ⌶    📋    🙂    ↶    ↷  |  ⌨
菜单   光标  剪贴板 表情 撤销 重做   收起键盘
```

| 按钮 | action | 说明 |
|---|---|---|
| `⋯` | `menu_keyboard` / 长按 `Settings` | 左端固定位（`primary_button`） |
| `⌶` | `Keyboard_editor` | 光标编辑面板 |
| `📋` | `clipboard_window` | 剪贴板 |
| `🙂` | `liquid_keyboard_emoji` | 表情 |
| `↶` | `undo` | 撤销 |
| `↷` | `redo_via_y` | 重做（预设的 `redo` 是死的，见下文） |
| `⌨` | `Hide` | 收起键盘 |

> **`buttons[0]` 的位置由代码决定，不由你写在第几位决定**，详见下文。

- `style: "ic@xxx"` 是同文内建图标（Iconics），会自动跟随配色着色
- 中英切换在键盘底行「数字」旁边；半/全角可在「方案」菜单里切
- **`Keyboard_editor` 不是同文自带的**，`trime.yaml` 里没有，
  得自己补预设键 + 一副叫 `editor` 的键盘（见下）。
  同文风主题里那副 `editor` 用了它私有的 `Left1`/`Shift_L2`/`Keyboard_bqsy*`
  和配色锚点，不能直接搬，所以重写了一副只用标准预设键的。

### 光标编辑键盘（`preset_keyboards/editor`）

```
全选   行首    ↑    行尾   上页
剪切    ←     ↓     →     下页
复制   删除   退格   撤销   重做
粘贴   Esc   符号   中/英  返回
```

5 列 x 4 行，每键宽 20，正好 100。方向键在第 1~2 行的中间三列，排成十字。

- `返回` 用的是自建的 `Keyboard_back`（`select: .last`），
  回到“上一副键盘”；不用 `.default`，因为那是 `smartMatchKeyboard()`，
  在符号页打开这个面板时会跳到字母键盘而不是符号页。
- 面板里的 `复制` 同样受下文 `Ctrl+C` 那个问题影响。

### ⚠️ 工具栏/长按里的 `action:` 是「预设键名」，不是命令名

```kotlin
// Theme.kt
fun resolveAction(tokenString: String) = resolveAction(KeyActionToken.Plain(tokenString))
// 内部：查 theme.presetKeys，查不到就当成字面文本发送
```

所以 `action: menu_keyboard` 能不能工作，取决于**主题里有没有叫 `menu_keyboard`
的预设键**。同文风主题有：

```yaml
menu_keyboard: { label: 菜单, send: FUNCTION, command: menu_keyboard }
```

而 `trime.yaml`（預設主题）没有 —— 直接写 `action: menu_keyboard` 会把
`menu_keyboard` 这串字当普通按键打出来。必须在 `trime.custom.yaml` 里补上这条预设键。

同理，任何 `long_click` / `swipe_*` / 工具栏 `action` 里写的不在 `preset_keys` 里的
多字符名字，都会退化成字面文本（单个字符如 `?` 本来就应该是字面文本）。

## 标点映射修正（`luna_pinyin*.custom.yaml`）

Rime 默认把 20 个 ASCII 符号在 `full_shape` / `half_shape` 下都转掉：

```
_  -> ——      @  -> ＠      *  -> ＊      (  -> （
'  -> ‘’      "  -> “”      |  -> ·       \  -> 、
/  -> ／/、    ?  -> ？      ;  -> ；      :  -> ：
```

注意 `_` 在 full_shape 和 half_shape **两个表里**都映射成 `——`，
所以「全角模式下不一致」其实半角下也会中招。

`/ ? ; :` 四个是后来数字面板用到才补进去的。

修法是在 schema 的 custom 文件里把这 20 个键改成原样提交：

```yaml
patch:
  "punctuator/half_shape/_": {commit: "_"}
  "punctuator/full_shape/_": {commit: "_"}
  ...（共 32 条）
```

必须写在 **schema 级**的 `luna_pinyin.custom.yaml` 里：标点表是 schema 自带的，
`default.custom.yaml` 改不到它。所以 luna_pinyin 和 luna_pinyin_simp 各一份。

## 想改的时候

- **改手势**：只改 `trime.custom.yaml` 里 `&dark26_keys` 那一份
  （`default` 和 `qwerty` 两个键盘 id 用 YAML 锚点指向同一份 keys，不用改两遍）。
- **想让长按也出大写**（百度习惯）：`{click: 'q', long_click: 'Q', label_symbol: '1', swipe_up: '1', swipe_down: 'Q'}`。
  注意 `label_symbol` 还在，角标不会变。
- **加方案**：在 `default.custom.yaml` 的 `schema_list` 里加；`stroke`（笔画）那行已写好，
  取消注释即可——但新方案如果要修标点，得再配一份 `<schema>.custom.yaml`。
- **每次改完都要在手机上重新部署**，否则 `build/` 不更新，前台看不到变化。

## 部署后怎么验证（离线/在机）

同文把合并结果写进 `files/rime/build/`，用它反查：

```bash
R=/sdcard/Android/data/com.osfans.trime/files/rime

# 补丁是否被读取（trime.custom 应是非 0 的时间戳）
adb shell head -6 $R/build/trime.yaml

# 我们的标记
adb shell grep -c '暗·26鍵' $R/build/trime.yaml     # 期望 2（default + qwerty）

# 关键：兄弟节点有没有被误伤
adb shell sed -n '/^preset_keyboards:/,/^preset_keys:/p' $R/build/trime.yaml | grep -cE '^  [a-z_0-9]+:'   # 期望 18
adb shell sed -n '/^style:/,/^[a-z]/p' $R/build/trime.yaml | grep -cE '^  [a-z_0-9]+:'                    # 期望 44

# 标点修正是否进了 schema
adb shell "sed -n '/^punctuator:/,/^recognizer:/p' $R/build/luna_pinyin.schema.yaml | grep -E '^    _:'"  # 期望 {commit: "_"}
```

截图测量键盘几何（需要 PIL 或 ffmpeg）：

```bash
adb exec-out screencap -p > /tmp/kb.png
ffmpeg -y -loglevel error -i /tmp/kb.png /tmp/kb2.png     # 转成 RGB，便于逐像素扫
```

## 候选区的三种形态，以及「展开时键盘会消失」的原因

同文其实有**三个**候选显示面，彼此独立：

| 形态 | 实现 | 与键盘的关系 |
|---|---|---|
| 紧凑候选栏 | `CompactCandidateDelegate`（`ime/candidates/compact/`） | 在候选栏里，键盘上方那一条 |
| **▼ 展开视图** | `FlexboxUnrolledCandidateWindow`（`ime/candidates/unrolled/`） | **替换键盘** |
| **浮动候选窗** | `CandidatesView` + `PagedCandidatesUi`（`ime/candidates/popup/`、`ime/composition/`） | **独立浮层，键盘保留** |

### ▼ 展开视图为什么必然挤掉键盘

它是个 `BoardWindow`，而所有 `BoardWindow` 共用**同一个槽位**：

```kotlin
// BoardWindowManager.kt:120
val view: FrameLayout by lazy { context.frameLayout(R.id.input_window) }
```

```kotlin
// InputView.kt:222 —— 这个槽位在 keyboardView 里被约束成「输入栏之下、底边留白之上」
add(
    windowManager.view,
    lParams {
        below(inputBar.view)
        above(bottomPaddingSpace)
    },
)
```

也就是**整块键盘区域**。键盘和展开视图是同一个槽位的两个住户，互斥。
所以「展开只占退格键上方、下面继续显示键盘」做不到 —— 没有任何配置能改它的大小或位置。
`windowManager.attachWindow(...)` 一次只挂一个窗口。

### 想要的效果：用浮动候选窗

> ⚠️ **已试过，结论是不好用，别再走这条路。**（2026-10-06 实测）
> 「始终显示」带来的浮窗位置/遮挡问题比它解决的问题多，最终决定保留原状的
> ▼ 展开（展开时键盘消失，认了）。下面保留技术记录，仅供将来翻查。

`CandidatesView` 通过 `inputDeviceManager.setCandidatesView(...)` 挂成**独立浮层**
（不是键盘槽位），所以键盘全程可用，空格/退格随便按。

它的候选列表是 `PagedCandidatesUi`：

```kotlin
// 多行铺开 + 翻页按钮
FlexboxLayoutManager(...)   // FlexWrap，会自动换行成多行
// 末尾追加一个 PaginationUi 项（◀ ▶ 图标）当有上一页/下一页时
```

三个可调项（都在 同文 → **Candidates Window** 页）：

| 设置 | 枚举 | 取值 |
|---|---|---|
| 显示候选窗口 | `PopupCandidatesMode` | 系统默认 / 依赖输入设备 / **始终显示** / 禁用（默认） |
| 候选列表布局 | `PopupCandidatesLayout` | 自动（默认）/ 横向 / 纵向 / 纵向逆序 |
| 候选窗口位置 | `PopupPosition` | 左下（默认）/ 右下 / 左上 / 右上 / **跟随光标** |

把第一项设成**「始终显示」**，就同时有了「大面积铺开候选」和「键盘可用」。

附带一个行为要知道：`ALWAYS_SHOW` 下 `InputView` 会把 composition 消息置空——

```kotlin
// InputView.kt:352
val data = if (candidatesMode == PopupCandidatesMode.ALWAYS_SHOW) {
    CompositionProto()      // ← 空
} else {
    it.data
}
```

因为编码/预编辑由浮窗自己显示，所以键盘上的内联拼音串会消失。这是有意为之，不是 bug。

> 顺带：这三个都是 SharedPreferences 项，`trime.yaml` 改不了，只能手动点。
> 想连紧凑候选栏也一起藏掉，可以再开 `hideInputBar`（同 Virtual Keyboard 页）。

## 已知问题

- **底部 120px 空白**：见上文——可以关（`Advanced` → `Ignore system gesture insets`），
  但关掉后空格键上滑会和系统「上滑回桌面」抢手势，所以故意保留。
- 同文预设的 `letter` 键盘（纯 ASCII 字段自动弹出的那个）用 `__include` 引用
  `preset_keyboards/default`，而 `__include` 在 patch 之前就解析完了，
  所以它仍是原来的 40 键布局。只在密码框之类的纯 ASCII 场景出现。
- 配色只覆盖了 `default`。如果之前在别的主题里选过别的配色，需要到
  同文 → 配色 → 选「纯暗／Pure Dark」。
- `ref/` 下的 `trime.yaml`、`tongwenfeng.trime.yaml` 来自同文输入法项目
  （Rime community），文件头标的是 **GPL-3.0-or-later**。
