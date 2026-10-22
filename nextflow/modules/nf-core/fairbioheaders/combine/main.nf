process FAIRBIOHEADERS_COMBINE {
    tag "${meta.id}"
    label 'process_single'

    conda "${moduleDir}/environment.yml"
    container "${ workflow.containerEngine in ['singularity', 'apptainer'] && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/fair-bioheaders:0.5.0--pyhdfd78af_0':
        'quay.io/biocontainers/fair-bioheaders:0.5.0--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(metadata), path(sequence)

    output:
    tuple val(meta), path("${prefix}.fh*"), emit: sequence
    tuple val("${task.process}"), val('fair-bioheaders'), eval("bioheaders --version"), emit: versions_fairbioheaders, topic: versions

    when:
    task.ext.when == null || task.ext.when

    script:
    def args = task.ext.args ?: ''
    prefix = task.ext.prefix ?: "${meta.id}"
    // Single-quote for the shell: file names and meta.id may hold any character.
    def quote = { value -> "'" + value.toString().replace("'", "'\\''") + "'" }
    def type = sequence.name ==~ /.*\.gfa(\.b?gz)?$/ ? 'gfa'
        : sequence.name ==~ /.*\.gff3?(\.b?gz)?$/ ? 'gff3' : 'fasta'
    // GFF3 carries the FHGFF3 header family; FASTA and GFA carry FHR.
    def header = type == 'gff3' ? 'fhgff3' : 'fhr'
    def extension = [gfa: 'gfa', gff3: 'gff3', fasta: 'fa'][type] + (sequence.name ==~ /.*\.b?gz$/ ? '.gz' : '')
    def output = quote.call("${prefix}.${header}.${extension}")
    """
    bioheaders combine \\
        --type ${type} \\
        ${args} \\
        --output ${output} \\
        ${quote.call(metadata)} \\
        ${quote.call(sequence)}
    """

    stub:
    prefix = task.ext.prefix ?: "${meta.id}"
    def quote = { value -> "'" + value.toString().replace("'", "'\\''") + "'" }
    def type = sequence.name ==~ /.*\.gfa(\.b?gz)?$/ ? 'gfa'
        : sequence.name ==~ /.*\.gff3?(\.b?gz)?$/ ? 'gff3' : 'fasta'
    def header = type == 'gff3' ? 'fhgff3' : 'fhr'
    def extension = [gfa: 'gfa', gff3: 'gff3', fasta: 'fa'][type]
    def gzipped = quote.call("${prefix}.${header}.${extension}.gz")
    def plain = quote.call("${prefix}.${header}.${extension}")
    def output = sequence.name ==~ /.*\.b?gz$/
        ? "echo '' | gzip > ${gzipped}"
        : "touch ${plain}"
    """
    ${output}
    """
}
