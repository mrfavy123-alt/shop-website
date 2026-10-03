import { handleApi } from '../api-lib.js';

export default {
  fetch(request) {
    return handleApi(request, '/api/products');
  },
};
