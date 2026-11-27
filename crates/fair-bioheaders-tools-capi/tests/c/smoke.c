/* Header smoke test: compiles against fhcore.h and links libfhcore. */
#include "fhcore.h"
#include <stdio.h>
#include <string.h>

int main(void) {
    if (fh_abi_major() != 0) return 10;
    fh_engine *engine = NULL;
    fh_error *err = NULL;
    if (fh_engine_new(NULL, &engine, &err) != FH_OK) return 11;
    const char *text = "a: [";
    fh_result *result = NULL;
    if (fh_verify_bytes(engine, FH_OP_VALIDATE, FH_C_METADATA_YAML, (const uint8_t *)text, strlen(text), &result, &err) != FH_OK) return 12;
    if (fh_result_outcome(result) != FH_OUTCOME_INVALID) return 13;
    if (fh_result_diagnostic_count(result) == 0) return 14;
    const uint8_t *p = NULL;
    size_t n = 0;
    if (fh_diag_text(result, 0, FH_DIAG_CODE, &p, &n) != FH_OK || n == 0 || p[n] != 0) return 15;
    printf("%.*s\n", (int)n, (const char *)p);
    fh_result_free(result);
    fh_engine_free(engine);
    fh_engine_free(NULL);
    return 0;
}
