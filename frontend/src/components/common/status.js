import {ClaimStatus,CertStatus} from '../../constants/enums.js';
import {esc} from '../../utils/dom.js';
export const status=v=>'<span class="status '+esc(v)+'">'+esc(ClaimStatus[v]||CertStatus[v]||v)+'</span>';
