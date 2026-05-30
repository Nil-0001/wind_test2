# 中远海特风电配载算法

*备注*：
1. 数据中距离和坐标统一为毫米mm。
2. 重量"weight"统一为吨t。
3. 坐标统一左下角为起点，顺时针一圈的顺序给出。

## 输入Input

- 测试数据: D:\Desktop\BaiduSyncdisk\Miluo\wind-stowage\wind_power_stowage\test\data\test_data.json
- 数据内容: cargoData待装载货物数据、vesselStructure船舶结构。其中vesselStructure船舶结构包括: bypassBoardPosition可以放置bypass盖板的位置、hatchCoverPosition舱盖板的位置、stowageFeasibleRange可以配载的空间范围。

## 输出Output

```json
{
    "totalSetCount": 10,
    "cargoPosition":[
        {
            "cargoType": "T110.5-70A",
            "cargoName": "Tower Section 1",
            "componentNo": 1,
            "cargoLabel": "Tower",
            "length": 8910,
            "width": 4550,
            "height": 4640,
            "weight": 72.6,
            "Layer": 1,
            "coordinate": {"1": {"x": -40149,"y": -842,"z": 0}, "2": {"x": -40149,"y": 31109,"z": 0}, "3": {"x": -40149,"y": 31109,"z": 0}, "4": {"x": -40149,"y": 31109,"z": 0}},
            "tier": 2,
            "direction": 1
        }
    ],
    "bypassBoardPosition":[
        {
                "1": {"x": 77.91,"y": 79.11,"z": 0},
                "2": {"x": 77.91,"y": 27379,"z": 0},
                "3": {"x": 4928,"y": 27379,"z": 0},
                "4": {"x": 4928,"y": 79.11,"z": 0},
                "layer": 2,
                "hatchno": 1,
                "label": 1
        }
    ]
}
```

- 输出的内容包括: totalSetCount配到船上的总套数，cargoPosition每件货物的位置，bypassBoardPosition启用的bypass板的位置。

## 概念模型

### 目标

- 最大化totalSetCount配到船上的总套数（凑齐"componentNo"1至6为一套）。

### 决策变量

1. 配载到船上的货物。
2. 配载到船上货物的"coordinate"坐标，从左下角顺时针4个坐标值；"Layer"船层；"tier"配一件还是两层两件；"direction"配载方向顺船还是横船，顺船计1横船计0。
3. 哪些bypassBoard被启用。

### 约束

1. 每件货物如果顺船，即"direction"为1，则可以在当前坐标位置一次配载两层，"tier"可为2，即两件（不能违反其他约束）；如果横船即"direction"为0，则只能配载一层，"tier"只能为1，即一件。
2. 配载到船上的货物必须成套，即必须能凑齐"componentNo"的1、2、3、4、5、6。不允许出现只放上部分构件的情况，最后总套数totalSetCount必须是整数。
3. 货物之间的左右间距必须大于100mm，即y轴方向上，排布货物，间隔必须大于100mm。或者说货物的上边和下边，这个上边和下边是相对的，如果顺船放，那么length边这个时候垂直y轴，就是上边和下边，这两边在y轴的坐标向上和向下100mm范围，自身x坐标区间辐射，（x1-x2）*100，不允许有其他货物的部分出现。
4. 货物之间的前后间距必须大于500mm，即x轴方向上，排布货物，间隔必须大于500mm。或者说货物的左边和右边，这个左边和右边是相对的，如果顺船放，那么width边这个时候垂直x轴，就是左边和右边，这两边在x轴的坐标向左和向右500mm范围，自身y坐标区间辐射，（y1-y2）*100，不允许有其他货物的部分出现。
5. 货物配载在"layer": 2、3、4时，货物的四个角的坐标点必须位于某块舱盖板hatchCover或某块bypassBoard圈出来的范围内。
6. 同块舱盖或bypassboard上不允许出现头对头的货物。即在"layer": 2、3、4时，货物的两端，即垂直x轴的两条边，必然担在某块舱盖板hatchCover或某块bypassBoard上，此时这两边范围，向左或右直到舱盖或bypassboard的边界的这范围，假设两边的长度范围（y1-y2），右侧边的x是x1，右侧舱盖边界x2，那么就是（y1-y2）*（x1-x2）的范围，不允许有其他货物的部分出现。
7. 货物的覆盖范围，包括四点圈出的平面范围和height的高度范围，tier为2时高度要乘以2，必须在可配载范围"stowageFeasibleRange"内，不能超出范围。"stowageFeasibleRange"给出了每层每个舱室，以及每层的以x或hatch分段的限高，layer4不限高。注意这个限高，我们要从layer1自底配到layer4，意味着下层在决策时是可以突破本层的限高的，比如layer1的"Hatch1"限高6329，如果这里配了两层某货物，高度可能为8000，那么再上层layer2这个货物垂直于x轴的两边，对应的两块bypassboard将不能启用，也就是说这个范围不能配载了，如果甚至超过layer2的高和layer1的高的和，那么layer3也不能启用对应的bypassboard了。但是注意layer3在配时则不能超过其自身限高，因为layer4的舱盖一定要盖。注意不只是板不能启用，这个货物自身范围整个空间也不能配货，也就是货和货不能重叠。
8. 货物配载在"layer": 2、3时，货物的四个角的坐标点必须位于某块bypassBoard圈出来的范围内。此时这两块bypassBoard被启用，被启用的bypassBoard总数不能超过18。
9. 货物配载在"layer": 1、2、3时，不能跨hatch，即货物的四个角坐标必须位于一个同个hatch范围内。
10. 每块舱盖或者被启用的bypassboard都有均布重量限制，即假设某块bypassboard上担着4件货物，那么这块bypassboard的均布承重为四件货物的重量的一半除以这块bypassboard的面积，此处面积要换算为平方米，均布强度不能超过3吨每平方米。

## 数学模型

### 参数

1. 