from typing import Optional
import logging
from .tagging.tagger import tag_synthesis
from .interpreting import extract_actions
from .finishing import action_list_to_xdl
from .logging import get_logger

#  python -m synthreader.synthreader.main


def text_to_xdl(synthesis_text: str, save_file: Optional[str] = None) -> str:
    """Convert synthesis text to XDL file of procedure described.

    Args:
        synthesis_text (str): Description of synthetic procedure.
        save_file (str): File path to save XDL to. Optional.

    Returns:
        str: Raw XDL str of synthesis text interpretation.
    """
    logger = get_logger()
    logger.setLevel(logging.INFO)
    logger.info('Tagging entities in text...')
    labelled_text = tag_synthesis(synthesis_text)
    logger.info('Extracting actions from tagged text...')
    action_list = extract_actions(labelled_text)
    logger.info('Converting actions to XDL...')
    xdl = action_list_to_xdl(action_list)
    if save_file:
        xdl.save(save_file)
        logger.info(f'Saved to {save_file}')
    return xdl

xdl = text_to_xdl("2,6-Dimethylaniline (3.0 mL, 2.9 g, 24.4 mmol) is added to 15 mL of glacial acetic acid followed by chloroacetyl chloride (2.0 mL, 2.85 g, 25.1 mmol) and 25 mL of half-saturated aqueous sodium acetate")

# 1. 去除冗余信息
# 2. 分句，分词，词性标注
# 3. 动作抽取。
# 4. XDL生成