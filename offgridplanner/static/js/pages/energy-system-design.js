/**
 * This script manages UI elements and SVG diagram interactions in a web application.
 * - Uses MutationObserver to display a modal when specific DOM changes occur.
 * - Defines and manipulates SVG elements for a dynamic energy system diagram.
 * - Enables and disables various options based on user input and system configuration.
 * - Dynamically styles SVG components (blocks, lines, arrows) based on user selections.
 * - Refreshes the diagram to reflect current system configuration, including energy sources and flow.
 */


const targetNode = document.getElementById('responseMsg');
const config = {childList: true, subtree: true, characterData: true};
const callback = function (mutationsList, observer) {
    for (let mutation of mutationsList) {
        if ((mutation.type === 'childList' || mutation.type === 'characterData') && targetNode.textContent.trim() !== '') {
            var modal = document.getElementById('msgBox');
            modal.style.display = "block";
        }
    }
};

const observer = new MutationObserver(callback);
observer.observe(targetNode, config);


const xLeft = 40;
var yTop = 130;
var roundCornerBlock = 5;
var roundCornerBus = 2;
var widthBlock = 125;
var widthBus = 10;
var heightBlock = 60;
var heightBus = 6 * heightBlock;
var lengthFlow = 90;

var lineCorrectionWidthBlock = 1;
var lineCorrectionLengthFlow = 1;

const component = [
    'pv',
    'battery',
    'diesel_genset',
    'inverter',
    'rectifier',
    'shortage',
    // 'surplus',
];

document.addEventListener('DOMContentLoaded', function () {
    refreshBlocksOnDiagramOnLoad();
    check_box_visibility('shortage');
    component.forEach(id => {
        var el = document.getElementById(assetCheckBox(id))
        el.addEventListener("click", () => check_box_visibility(id));
        el.addEventListener("click", () => refreshBlocksOnDiagram(id));
    });
});

/************************************************************/
/*                ENABLING DISABLING OPTIONS                */

/************************************************************/

function assetCheckBox(id) {
    return "id_" + id + "_settings_is_selected"
}

function optimizationCheckBox(id) {
    return id + "_settings_design_optimized"
}

function check_optimization_strategy(id) {
    // Update the styles after changing the optimization strategy
    styleBlock(id);
    styleText(id);
    styleLine(id);
    styleArrow(id);
    styleInformation(id);

    if (document.getElementById(optimizationCheckBox(id)).checked) {
        document.getElementById("id_" + id + "_parameters_nominal_capacity").readOnly = true;
        document.getElementById(id + "_parameters_nominal_capacity_label").classList.add('greyed');
        document.getElementById(id + "_parameters_nominal_capacity_label").classList.add('disabled');
        document.getElementById(id + "_parameters_nominal_capacity_unit").classList.add('greyed');
        document.getElementById(id + "_parameters_nominal_capacity_unit").classList.add('disabled');
    } else {
        document.getElementById("id_" + id + "_parameters_nominal_capacity").readOnly = false;
        document.getElementById(id + "_parameters_nominal_capacity_label").classList.remove('greyed');
        document.getElementById(id + "_parameters_nominal_capacity_label").classList.remove('disabled');
        document.getElementById(id + "_parameters_nominal_capacity_unit").classList.remove('greyed');
        document.getElementById(id + "_parameters_nominal_capacity_unit").classList.remove('disabled');
    }
}

function check_box_visibility(id) {
    const inverter = document.getElementById(assetCheckBox('inverter'));
    const pv = document.getElementById(assetCheckBox('pv'));
    const battery = document.getElementById(assetCheckBox('battery'));

    const isChecked = (element) => element && element.checked;

    if (id === 'inverter' && !isChecked(inverter)) {
        pv.checked = false;
        battery.checked = false;
        ['pv', 'battery'].forEach(item => {
            change_box_visibility(item);
            refreshBlocksOnDiagram(item);
        });
    }

    if ((id === 'pv' && isChecked(pv)) || (id === 'battery' && isChecked(battery))) {
        inverter.checked = true;
        change_box_visibility('inverter');
        refreshBlocksOnDiagram('inverter');
    }

    if (!isChecked(pv) && !isChecked(battery)) {
        inverter.checked = false;
        change_box_visibility('inverter');
        refreshBlocksOnDiagram('inverter');
    }
    change_box_visibility(id);
}


function change_box_visibility(id) {
    let checkBox = document.getElementById(assetCheckBox(id));
    let box = document.getElementById("select" + toTitleCase(id) + "Box");

    if (!checkBox || !box) return;

    let isChecked = checkBox.checked;

    // Update the box's selected state
    box.classList.toggle('box--not-selected', !isChecked);

    // Find all relevant input fields within the box
    let inputs = box.querySelectorAll("input:not(.form-check-input), select, textarea, button");
    let labels = box.querySelectorAll("label, span.input-group-text");

    inputs.forEach(input => {
        if (!isChecked) {
            input.readOnly = true;
            input.classList.add('readonly-disabled');
        } else {
            input.readOnly = false;
            input.classList.remove('readonly-disabled');
        }
    });

    labels.forEach(label => {
        label.classList.toggle('readonly-disabled', !isChecked);
    });

    // Check optimization strategy if applicable
    if (id !== "shortage") {
        check_optimization_strategy(id);
    }
}

function refreshBlocksOnDiagramOnLoad() {
    component.forEach(id => {
        refreshBlocksOnDiagram(id);
        if (id !== 'shortage') {
            // if (id !== 'shortage' && component [i] !== 'surplus'){
            check_box_visibility(id);
            check_optimization_strategy(id);
        } else {
            change_box_visibility(id);
        }
    });
    refreshBlocksOnDiagram('demand');
}


/************************************************************/
/*                 DRAW AND STYLE THE BLOCKS                */

/************************************************************/
function drawBlock(id, x, y) {
    const block = document.getElementById("block" + toTitleCase(id));

    if (id.slice(2, 6) === "Bus") {
        rxy = roundCornerBus;
        width = widthBus;
        height = heightBus;
    } else {
        rxy = roundCornerBlock;
        width = widthBlock;
        height = heightBlock;
    }

    block.setAttribute('x', x);
    block.setAttribute('y', y);
    block.setAttribute('rx', rxy);
    block.setAttribute('ry', rxy);
    block.setAttribute('width', width);
    block.setAttribute('height', height);
}

function styleBlock(id) {
    const block = document.getElementById("block" + toTitleCase(id));
    if (id === 'demand') {
        block.classList.add('components-block--demand');
    } else if (id === 'shortage') {
        // } else if (id === 'shortage' || id === 'surplus') {
        block.classList.add('components-block--constraints');
    } else if (document.getElementById(optimizationCheckBox(id)).checked) {
        block.classList.remove('components-block--dispatch');
        block.classList.add('components-block--design');
    } else {
        block.classList.remove('components-block--design');
        block.classList.add('components-block--dispatch');
    }
}


/************************************************************/
/*                    WRITE THE BLOCK TEXT                  */

/************************************************************/
function writeText(id, x, y) {
    const text = document.getElementById("text" + toTitleCase(id));

    text.setAttribute('x', x);
    text.setAttribute('y', y);
}

function writeInformation(id, x, y) {
    const information = document.getElementById("information" + toTitleCase(id));

    if (id !== 'demand') {
        information.setAttribute('x', x);
        information.setAttribute('y', y);
        if (id == 'shortage') {
            const informationSecondLine = document.getElementById("information" + toTitleCase(id) + "SecondLine");
            informationSecondLine.setAttribute('x', x);
            informationSecondLine.setAttribute('y', 0.9 * y);
        }
    }
}

function styleText(id) {
    const text = document.getElementById("text" + toTitleCase(id));

    if (id === 'demand') {
        text.classList.add('components-text--demand');
    } else if (id === 'shortage') {
        // } else if (id === 'shortage' || id === 'surplus') {
        text.classList.add('components-text--constraints');
    } else if (document.getElementById(optimizationCheckBox(id)).checked) {
        text.classList.remove('components-text--dispatch');
        text.classList.add('components-text--design');
    } else {
        text.classList.remove('components-text--design');
        text.classList.add('components-text--dispatch');
    }

}

function styleInformation(id) {
    const information = document.getElementById("information" + toTitleCase(id));
    if (!information) return; // Exit if the element does not exist

    if (id === 'shortage') {
        const secondLine = document.getElementById("information" + toTitleCase(id) + "SecondLine");
        const maxTotal = document.getElementById("id_shortage_parameters_max_shortage_total")?.value;
        const maxTimestep = document.getElementById("id_shortage_parameters_max_shortage_timestep")?.value;
        const unit = document.getElementById("shortage_parameters_max_shortage_timestep_unit")?.innerText;
        information.textContent = `max. each timestep ${maxTimestep} ${unit}`;
        if (secondLine) {
            secondLine.textContent = `max. total ${maxTotal} ${unit}`;
            secondLine.classList.add('components-information--constraints');
        }
        information.classList.add('components-information--constraints');
    } else {
        const optCheckbox = document.getElementById(optimizationCheckBox(id));
        if (optCheckbox?.checked) {
            information.textContent = "optimized capacity";
            information.classList.replace('components-information--dispatch', 'components-information--design');
        } else {
            const capacity = document.getElementById("id_" + id + "_parameters_nominal_capacity")?.value;
            const unit = document.getElementById(id + "_parameters_nominal_capacity_unit")?.innerText;
            information.textContent = `fixed capacity - ${capacity} ${unit}`;
            information.classList.replace('components-information--design', 'components-information--dispatch');
        }
    }
}

function drawLine(id, linePoints1, linePoints2) {
    // Lines always start from one side of the blocks and end at the bus

    // id is in form of for example linePV or lineDieselGenset
    const line1 = document.getElementById("line" + toTitleCase(id));

    line1.setAttribute('x1', linePoints1[0][0]);
    line1.setAttribute('y1', linePoints1[0][1]);
    line1.setAttribute('x2', linePoints1[1][0]);
    line1.setAttribute('y2', linePoints1[1][1]);

    // For inverter and rectifier there should be two lines.
    if (linePoints2.length > 0) {
        const line2 = document.getElementById("line" + toTitleCase(id) + "2");

        line2.setAttribute('x1', linePoints2[0][0]);
        line2.setAttribute('y1', linePoints2[0][1]);
        line2.setAttribute('x2', linePoints2[1][0]);
        line2.setAttribute('y2', linePoints2[1][1]);
    }
}

function styleLine(id) {
    const line1 = document.getElementById("line" + toTitleCase(id));

    if (id === 'demand') {
        line1.classList.add('components-flow--demand');
    } else if (id === 'shortage') {
        // } else if (id === 'shortage' || id === 'surplus') {
        line1.classList.add('components-flow--constraints');
    } else if (document.getElementById(optimizationCheckBox(id)).checked) {
        line1.classList.remove('components-flow--dispatch');
        line1.classList.add('components-flow--design');
    } else {
        line1.classList.remove('components-flow--design');
        line1.classList.add('components-flow--dispatch');
    }

    // For inverter and rectifier there should be two lines.
    if (id === "inverter" || id === "rectifier") {
        const line2 = document.getElementById("line" + toTitleCase(id) + "2");

        if (document.getElementById(optimizationCheckBox(id)).checked) {
            line2.classList.remove('components-flow--dispatch');
            line2.classList.add('components-flow--design');

        } else {
            line2.classList.remove('components-flow--design');
            line2.classList.add('components-flow--dispatch');
        }
    }
}

function drawArrow(id, arrowOutPoints1, arrowInPoints1, arrowOutPoints2, arrowInPoints2) {
    // The default arrow is the `arrowOut` which always at the end of the line,
    // that means it is outward (block ---> bus ).
    // Another type of arrow is called `arrowIn`, which corresponds to the arrows
    // entering a block (bus ---> block).

    // points should be in the format [[x1,y1], [x2,y2], [x3,y3]]
    const arrowOut1 = document.getElementById("arrowOut" + toTitleCase(id));
    const arrowIn1 = document.getElementById("arrowIn" + toTitleCase(id));

    arrowOut1.setAttribute('points', arrowOutPoints1);
    arrowIn1.setAttribute('points', arrowInPoints1);

    // For inverter and rectifier there are two lines and therefore, two arrows are required
    if (arrowOutPoints2.length > 0) {
        const arrowOut2 = document.getElementById("arrowOut" + toTitleCase(id) + "2");
        const arrowIn2 = document.getElementById("arrowIn" + toTitleCase(id) + "2");

        arrowOut2.setAttribute('points', arrowOutPoints2);
        arrowIn2.setAttribute('points', arrowInPoints2);
    }
}

function styleArrow(id) {
    const arrowOut1 = document.getElementById("arrowOut" + toTitleCase(id));
    const arrowIn1 = document.getElementById("arrowIn" + toTitleCase(id));

    if (id === 'demand') {
        $(arrowOut1).attr("visibility", "hidden");
        arrowIn1.classList.add('components-flow--demand');
    } else if (id === 'shortage') {
        $(arrowIn1).attr("visibility", "hidden");
        arrowOut1.classList.add('components-flow--constraints');
        // } else if (id === 'surplus') {
        //     $(arrowOut1).attr("visibility", "hidden");
        //     arrowIn1.classList.add('components-flow--constraints');
    } else if (document.getElementById(optimizationCheckBox(id)).checked) {
        if (id === 'pv' || id === 'diesel_genset' || id === 'shortage') {
            $(arrowIn1).attr("visibility", "hidden");
            arrowOut1.classList.remove('components-flow--dispatch');
            arrowOut1.classList.add('components-flow--design');
        } else if (id === 'battery') {
            arrowOut1.classList.remove('components-flow--dispatch');
            arrowIn1.classList.remove('components-flow--dispatch');
            arrowOut1.classList.add('components-flow--design');
            arrowIn1.classList.add('components-flow--design');
        } else {
            const arrowOut2 = document.getElementById("arrowOut" + toTitleCase(id) + "2");
            const arrowIn2 = document.getElementById("arrowIn" + toTitleCase(id) + "2");
            if (id === 'rectifier') {
                $(arrowOut1).attr("visibility", "hidden");
                $(arrowIn2).attr("visibility", "hidden");
                arrowOut2.classList.remove('components-flow--dispatch');
                arrowIn1.classList.remove('components-flow--dispatch');
                arrowOut2.classList.add('components-flow--design');
                arrowIn1.classList.add('components-flow--design');
            } else {
                $(arrowOut2).attr("visibility", "hidden");
                $(arrowIn1).attr("visibility", "hidden");
                arrowOut1.classList.remove('components-flow--dispatch');
                arrowIn2.classList.remove('components-flow--dispatch');
                arrowOut1.classList.add('components-flow--design');
                arrowIn2.classList.add('components-flow--design');
            }
        }
        ;
    } else {
        if (id === 'pv' || id === 'diesel_genset' || id === 'shortage') {
            $(arrowIn1).attr("visibility", "hidden");
            arrowOut1.classList.add('components-flow--dispatch');
            arrowOut1.classList.remove('components-flow--design');
        } else if (id === 'battery') {
            arrowOut1.classList.add('components-flow--dispatch');
            arrowIn1.classList.add('components-flow--dispatch');
            arrowOut1.classList.remove('components-flow--design');
            arrowIn1.classList.remove('components-flow--design');
        } else {
            const arrowOut2 = document.getElementById("arrowOut" + toTitleCase(id) + "2");
            const arrowIn2 = document.getElementById("arrowIn" + toTitleCase(id) + "2");
            if (id === 'inverter') {
                $(arrowOut1).attr("visibility", "hidden");
                $(arrowIn2).attr("visibility", "hidden");
                arrowOut2.classList.add('components-flow--dispatch');
                arrowIn1.classList.add('components-flow--dispatch');
                arrowOut2.classList.remove('components-flow--design');
                arrowIn1.classList.remove('components-flow--design');
            } else {
                $(arrowOut2).attr("visibility", "hidden");
                $(arrowIn1).attr("visibility", "hidden");
                arrowOut1.classList.add('components-flow--dispatch');
                arrowIn2.classList.add('components-flow--dispatch');
                arrowOut1.classList.remove('components-flow--design');
                arrowIn2.classList.remove('components-flow--design');
            }
        }
        ;
    }

    // For inverter and rectifier there should be two lines.
    if (id === "inverter" || id === "rectifier") {
        const line2 = document.getElementById("line" + toTitleCase(id) + "2");

        if (document.getElementById(optimizationCheckBox(id)).checked) {
            line2.classList.remove('components-flow--dispatch');
            line2.classList.add('components-flow--design');

        } else {
            line2.classList.remove('components-flow--design');
            line2.classList.add('components-flow--dispatch');
        }
    }

}

function refreshBusesOnDiagram() {
    // This function draw/remove AC and DC buses and their texts in the diagram
    // depending on if the attached blocks to them are selected or not.
    const groupDcBus = document.getElementById("groupDcBus");
    const groupAcBus = document.getElementById("groupAcBus");

    var busCoordinates = {
        'dcBus': {
            'x': xLeft + widthBlock + lengthFlow,
            'y': yTop - heightBlock,
        },
        'acBus': {
            'x': xLeft + 2 * widthBlock + 3 * lengthFlow + widthBus,
            'y': yTop - heightBlock,
        },
    };

    const selectPv = document.getElementById(assetCheckBox("pv")).checked;
    const selectBattery = document.getElementById(assetCheckBox("battery")).checked;
    const selectInverter = document.getElementById(assetCheckBox("inverter")).checked;
    const selectRectifier = document.getElementById(assetCheckBox("rectifier")).checked;

    // Since there is always demand, AC bus is always visible
    $(groupAcBus).attr("visibility", "visible");
    drawBlock(
        id = "acBus",
        x = busCoordinates.acBus.x,
        y = busCoordinates.acBus.y,
    )
    writeText(
        id = "acBus",
        x = busCoordinates.acBus.x + 0.5 * widthBus,
        y = 0.7 * busCoordinates.acBus.y
    )

    // DC bus is not necessarily always visible
    if (selectPv || selectBattery || selectInverter || selectRectifier) {
        $(groupDcBus).attr("visibility", "visible");
        drawBlock(
            id = "dcBus",
            x = busCoordinates.dcBus.x,
            y = busCoordinates.dcBus.y,
        )
        writeText(
            id = "dcBus",
            x = busCoordinates.dcBus.x + 0.5 * widthBus,
            y = 0.7 * busCoordinates.dcBus.y
        )
    } else {
        // First make the SVG group visible
        $(groupDcBus).attr("visibility", "hidden");
    }

}

function refreshBlocksOnDiagram(id) {
    // This function draw/remove all blocks and their texts and flows in the diagram depending on
    // if they are selected by user or not.
    // For AC and DC buses, the function `refreshBusesOnDiagram` does the same work.
    const groupId = document.getElementById("group" + toTitleCase(id));

    if (id === 'demand') {
        var isSelected = true;
    } else if (id === 'shortage') {
        // } else if (id === 'shortage' || id === 'surplus') {
        if (document.getElementById(assetCheckBox("shortage")).checked) {
            var isSelected = document.getElementById(assetCheckBox(id)).checked;
        } else {
            var isSelected = false;
        }
    } else {
        var isSelected = document.getElementById(assetCheckBox(id)).checked;
    }

    var blockCoordinates = {
        'pv': {
            'x': xLeft,
            'y': yTop,
        },
        'battery': {
            'x': xLeft,
            'y': yTop + 3 * heightBlock,
        },
        'inverter': {
            'x': xLeft + widthBlock + 2 * lengthFlow + widthBus,
            'y': yTop - 0.5 * heightBlock,
        },
        'rectifier': {
            'x': xLeft + widthBlock + 2 * lengthFlow + widthBus,
            'y': yTop - 0.5 * heightBlock + 2 * heightBlock,
        },
        'diesel_genset': {
            'x': xLeft + widthBlock + 2 * lengthFlow + widthBus,
            'y': yTop - heightBlock / 2 + 4 * heightBlock,
        },
        'shortage': {
            'x': xLeft + 2 * widthBlock + 4 * lengthFlow + 2 * widthBus,
            'y': yTop + 0.5 * heightBlock,
        },
        'demand': {
            'x': xLeft + 2 * widthBlock + 4 * lengthFlow + 2 * widthBus,
            'y': yTop - heightBlock + 3.5 * heightBlock,
        },
        'surplus': {
            'x': xLeft + 2 * widthBlock + 4 * lengthFlow + 2 * widthBus,
            'y': yTop - heightBlock + 5 * heightBlock,
        },
    };

    if (isSelected) {
        // First make the SVG group visible
        $(groupId).attr("visibility", "visible");

        /**************/
        /*   BLOCKS   */
        /**************/
        drawBlock(
            id = id,
            x = blockCoordinates[id].x,
            y = blockCoordinates[id].y,
        )
        styleBlock(id = id);

        /*************/
        /*   TEXTS   */
        /*************/
        writeText(
            id = id,
            x = blockCoordinates[id].x + 0.5 * widthBlock,
            y = blockCoordinates[id].y + 0.5 * heightBlock
        )
        styleText(id);

        writeInformation(
            id = id,
            x = blockCoordinates[id].x,
            y = blockCoordinates[id].y - 0.1 * heightBlock,
        );
        styleInformation(id);


        /***********************/
        /*   LINES AND ARROWS  */
        /***********************/
        if (id === 'demand' || id === 'shortage') {
            // if (id === 'demand' || id === 'surplus' || id === 'shortage') {
            lineCorrectionWidthBlock = 0;
            lineCorrectionLengthFlow = -1;
        } else {
            lineCorrectionWidthBlock = 1;
            lineCorrectionLengthFlow = 1;
        }
        ;
        linePoints1 = [
            [blockCoordinates[id].x + lineCorrectionWidthBlock * widthBlock, blockCoordinates[id].y + 0.5 * heightBlock],
            [blockCoordinates[id].x + lineCorrectionWidthBlock * widthBlock + lineCorrectionLengthFlow * lengthFlow, blockCoordinates[id].y + 0.5 * heightBlock]
        ];

        arrowOutPoints1 = [
            [
                linePoints1[1][0] - lineCorrectionLengthFlow * 0.15 * lengthFlow,
                linePoints1[1][1] - lineCorrectionLengthFlow * 0.1 * lengthFlow
            ],
            [linePoints1[1][0], linePoints1[1][1]],
            [
                linePoints1[1][0] - lineCorrectionLengthFlow * 0.15 * lengthFlow,
                linePoints1[1][1] + lineCorrectionLengthFlow * 0.1 * lengthFlow
            ],
        ];

        arrowInPoints1 = [
            [
                linePoints1[0][0] + lineCorrectionLengthFlow * 0.15 * lengthFlow,
                linePoints1[0][1] - lineCorrectionLengthFlow * 0.1 * lengthFlow
            ],
            [linePoints1[0][0], linePoints1[1][1]],
            [
                linePoints1[0][0] + lineCorrectionLengthFlow * 0.15 * lengthFlow,
                linePoints1[0][1] + lineCorrectionLengthFlow * 0.1 * lengthFlow
            ],
        ];

        // For inverter and rectifier there would be two lines
        if (id === "inverter" || id === "rectifier") {
            lineCorrectionWidthBlock = 0;
            lineCorrectionLengthFlow = -1;
            linePoints2 = [
                [blockCoordinates[id].x + lineCorrectionWidthBlock * widthBlock, blockCoordinates[id].y + 0.5 * heightBlock],
                [blockCoordinates[id].x + lineCorrectionWidthBlock * widthBlock + lineCorrectionLengthFlow * lengthFlow, blockCoordinates[id].y + 0.5 * heightBlock]
            ];

            arrowOutPoints2 = [
                [
                    linePoints2[1][0] - lineCorrectionLengthFlow * 0.15 * lengthFlow,
                    linePoints2[1][1] - lineCorrectionLengthFlow * 0.1 * lengthFlow
                ],
                [linePoints2[1][0], linePoints2[1][1]],
                [
                    linePoints2[1][0] - lineCorrectionLengthFlow * 0.15 * lengthFlow,
                    linePoints2[1][1] + lineCorrectionLengthFlow * 0.1 * lengthFlow
                ],
            ];

            arrowInPoints2 = [
                [
                    linePoints2[0][0] + lineCorrectionLengthFlow * 0.15 * lengthFlow,
                    linePoints2[0][1] - lineCorrectionLengthFlow * 0.1 * lengthFlow
                ],
                [linePoints2[0][0], linePoints2[1][1]],
                [
                    linePoints2[0][0] + lineCorrectionLengthFlow * 0.15 * lengthFlow,
                    linePoints2[0][1] + lineCorrectionLengthFlow * 0.1 * lengthFlow
                ],
            ];
        } else {
            linePoints2 = [];
            arrowOutPoints2 = [];
            arrowInPoints2 = [];
        }
        drawLine(
            id = id,
            linePoints1 = linePoints1,
            linePoints2 = linePoints2
        )
        styleLine(id);

        drawArrow(
            id = id,
            arrowOutPoints1 = arrowOutPoints1,
            arrowInPoints1 = arrowInPoints1,
            arrowOutPoints2 = arrowOutPoints2,
            arrowInPoints2 = arrowInPoints2,
        )
        styleArrow(id);

    } else {
        $(groupId).attr("visibility", "hidden");
    }

    refreshBusesOnDiagram();
}

function toTitleCase(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}
