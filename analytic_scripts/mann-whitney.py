import pandas as pd
from scipy import stats
from numpy import nanmedian
import rpy2.robjects as robjects
from rpy2.robjects.packages import importr

def bonferroniCorrection(p_value, num_tests):
    if p_value * num_tests < 1:
        return p_value * num_tests
    return 1

def effectSize(series1, series2, rcliff):
    list1 = robjects.FloatVector(list(series1))
    list2 = robjects.FloatVector(list(series2))
    magnitude = rcliff(list1, list2).rx('magnitude')[0].levels[0]
    #print rcliff(list1, list2).names
    estimate = round(rcliff(list1, list2).rx('estimate')[0][0], 2)
    return '%.2f|%s' %(estimate, magnitude)

def statisticalAnalyses(df_sub1, df_sub2, metric_list):
    # import R packages
    effsize = importr('effsize')
    rcliff = robjects.r['cliff.delta']
    # list to save the results
    result_list = list()
    # Wilcoxon rank sum test & effect size
    num_tests = len(metric_list)
    for metric in metric_list:
        statistic,p_value = stats.mannwhitneyu(df_sub1[metric], df_sub2[metric])
        corrected_p = bonferroniCorrection(p_value, num_tests)
        effect_size = '--'
        if corrected_p < 0.05:
            effect_size = effectSize(df_sub1[metric], df_sub2[metric], rcliff)            
        sub1_median = nanmedian(df_sub1[metric])
        sub2_median = nanmedian(df_sub2[metric])
        result_list.append([metric, sub1_median, sub2_median, corrected_p, effect_size])
    return result_list

if __name__ == '__main__':
    # load data
    print 'Loading data ...'
    df_crash_inducing = pd.read_csv('../new_statistics/crash_inducing_issues.csv')
    df_basic = pd.read_csv('../new_statistics/basic_metrics.csv')
    df_review = pd.read_csv('../new_statistics/review_metrics2.csv')
    df = pd.merge(df_basic, df_crash_inducing, on='bug_id')
    df = pd.merge(df, df_review, on='bug_id')
    df = df[df.reviewed == '+']
    df = df.drop('caused_bugs', 1)
    df = df.drop('reviewer_origin', 1)
    df_crash = df[df.crash_inducing == True]
    df_clean = df[df.crash_inducing == False]
    
    for col in df.columns.values:
        if col not in ['reviewed', 'bug_id']:
            print col, nanmedian(df[col])
    
    # Wilcoxon rank sum test & effect size
    print 'Statistical analyses ...'
    metric_list = ['patch_size', 'changed_files', 'LOC', 'mccabe', 'cnt_func',
                    'max_nesting', 'ratio_comment', 'page_rank', 'betweenness',
                    'closeness', 'indegree', 'outdegree', 
                    'review_iterations', 'comment_times', 'comment_words', 'reviewers',
                    'reviewer_comment_rate', 'neg_review_rate', 'response_delay',
                    'review_duration', 'obsolete_rate', 'feedback_count', 'neg_feedback']
    result_list = statisticalAnalyses(df_crash, df_clean, metric_list)
    df = pd.DataFrame(result_list, columns=['metric', 'crash', 'clean', 'p-value', 'effect_size'])
    print df
