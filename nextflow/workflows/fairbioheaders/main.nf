#!/usr/bin/env nextflow
// SPDX-License-Identifier: MPL-2.0
// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.
//
// Adds FAIR-bioHeaders metadata to FASTA, GFA or GFF3 files and verifies the result:
// FAIRBIOHEADERS_COMBINE writes the headed file with its checksum, then
// FAIRBIOHEADERS_VERIFY checks the header against the schema and the checksum.
// See README.md in this directory for the parameters.

include { FAIRBIOHEADERS_COMBINE } from '../../modules/nf-core/fairbioheaders/combine/main'
include { FAIRBIOHEADERS_VERIFY  } from '../../modules/nf-core/fairbioheaders/verify/main'

// A samplesheet path: a URL or absolute path as is, otherwise relative to the sheet.
// The sheet itself may be a URL, such as the raw GitHub URL of the test samplesheet.
def sheetFile(sheet, String path) {
    if (path.contains('://') || path.startsWith('/')) {
        return file(path, checkIfExists: true)
    }
    def resolved = sheet.parent.resolve(path).normalize()
    if (!resolved.exists()) {
        error("Samplesheet ${sheet.toUriString()}: no such file: ${resolved.toUriString()}")
    }
    return resolved
}

workflow {
    main:
    def input
    if (params.input) {
        // Samplesheet: CSV with the columns id,metadata,sequence. Relative paths are
        // relative to the samplesheet's directory.
        def sheet = file(params.input, checkIfExists: true)
        input = channel.fromPath(sheet)
            .splitCsv(header: true, strip: true)
            .map { row ->
                if (!row.id || !row.metadata || !row.sequence) {
                    error("Samplesheet ${params.input}: each row needs id, metadata and sequence: ${row}")
                }
                [[id: row.id], sheetFile(sheet, row.metadata), sheetFile(sheet, row.sequence)]
            }
    } else if (params.metadata && params.sequence) {
        def sequence = file(params.sequence, checkIfExists: true)
        def id = params.id ?: sequence.name.replaceFirst(/(\.(fa|fasta|fna|gfa|gff3?))?(\.b?gz)?$/, '')
        input = channel.of([[id: id], file(params.metadata, checkIfExists: true), sequence])
    } else {
        error("Give --input samplesheet.csv, or --metadata and --sequence (see README.md).")
    }

    FAIRBIOHEADERS_COMBINE(input)
    FAIRBIOHEADERS_VERIFY(FAIRBIOHEADERS_COMBINE.out.sequence)
}
